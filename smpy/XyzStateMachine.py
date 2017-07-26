from enum import Enum
import uuid


class XyzState(Enum):
    #BEGIN_HANDLEBARS
    #{{#each states}}
    #    {{this}} = '{{this}}'
    #{{/each}}
    DEFAULT = 'DEFAULT'
    RUNNING = 'RUNNING'
    STOPPED = 'STOPPED'
    #END_HANDLEBARS


STATE_INDEX = {
    'DEFAULT': 0,
    'RUNNING': 1,
    'STOPPED': 2,
}


class XyzStateChangeEvent(object):
    def __init__(self, previous_state, target_state, data):
        self._previousState = previous_state
        self._targetState = target_state
        self.data = data
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def cancelled(self):
        return self._cancelled

    @property
    def previousState(self):
        return self._previousState

    @property
    def targetState(self):
        return self._targetState


class XyzStateException(Exception):
    pass


transition_set = dict()
link_map = dict()


def register_transition(name, fromState, toState):
    transition_set[STATE_INDEX[fromState.value] << 16 | STATE_INDEX[toState.value]] = True

    if not name:
        return

    fromMap = link_map.get(fromState.value)

    if not fromMap:
        fromMap = link_map[fromState.value] = dict()

    fromMap[name] = toState

# BEGIN_TRANSITIONS: register_transition("TRANSITION_NAME", XyzState.FROM_STATE, XyzState.TO_STATE);
register_transition("run", XyzState.DEFAULT, XyzState.RUNNING);
register_transition(None, XyzState.DEFAULT, XyzState.STOPPED);
register_transition(None, XyzState.RUNNING, XyzState.DEFAULT);
register_transition(None, XyzState.RUNNING, XyzState.STOPPED);
register_transition(None, XyzState.RUNNING, XyzState.RUNNING);
# END_TRANSITIONS

class XyzStateMachine(object):
    def __init__(self, initialState=None):
        self.transitionListeners = dict()
        self.dataListeners = dict()
        #BEGIN_HANDLEBARS
        #        self.initialState = initialState || XyzState.{{states.[0]}}
        self._initalState = initialState or XyzState.DEFAULT
        #END_HANDLEBARS
        self._currentState = None

        self.transitionListeners['DEFAULT'] = EventListener()
        self.transitionListeners['RUNNING'] = EventListener()
        self.transitionListeners['STOPPED'] = EventListener()
        self.dataListeners['DEFAULT'] = EventListener()
        self.dataListeners['RUNNING'] = EventListener()
        self.dataListeners['STOPPED'] = EventListener()

        self.currentChangeStateEvent = None

    @property
    def state(self):
        self._ensure_state_machine_initialized()
        return self._currentState

    def run(self, data = None):
        return self.transition("run", data)

    def _ensure_state_machine_initialized(self):
        if not self._currentState:
            self._change_state_impl(self._initalState, None)

    def changeState(self, targetState, data = None):
        self._ensure_state_machine_initialized()
        return self._change_state_impl(targetState, data)

    def _change_state_impl(self, targetState, data = None):
        if not targetState:
            raise Exception("No target state specified. Can not change the state.")

        # this also ignores the fact that maybe there is no transition
        # into the same state.
        if targetState == self._currentState:
            return targetState

        state_change_event = XyzStateChangeEvent(self._currentState, targetState, data)

        if self.currentChangeStateEvent:
            raise XyzStateException(
                "The XyzStateMachine is already in a changeState (%s -> %s). "
                "Transitioning the state machine (%s -> %s) in `before` events is not supported." % (
                    self.currentChangeStateEvent.previousState.value,
                    self.currentChangeStateEvent.targetState.value,
                    self._currentState.value,
                    targetState.value
                ))

        if self._currentState and not transition_set.get(STATE_INDEX[self._currentState.value] << 16 | STATE_INDEX[targetState.value]):
            print("No transition exists between %s -> %s." % (self._currentState.value, targetState.value))
            return self._currentState

        self.currentChangeStateEvent = state_change_event

        if state_change_event.previousState:
            self.transitionListeners[state_change_event.previousState.value].fire(EventType.BEFORE_LEAVE, state_change_event)

        self.transitionListeners[state_change_event.targetState.value].fire(EventType.BEFORE_ENTER, state_change_event)

        if state_change_event.cancelled:
            return self._currentState

        self._currentState = targetState
        self.currentChangeStateEvent = None

        if state_change_event.previousState:
            self.transitionListeners[state_change_event.previousState.value].fire(EventType.AFTER_LEAVE, state_change_event)

        self.transitionListeners[state_change_event.targetState.value].fire(EventType.AFTER_ENTER, state_change_event)

        return self._currentState

    def transition(self, linkName, data = None):
        self._ensure_state_machine_initialized()

        sourceState = link_map.get(self._currentState.value)

        if not sourceState:
            return None

        targetState = sourceState[linkName]

        if not targetState:
            return None

        return self.changeState(targetState, data)

    def before_enter(self, state, callback):
        return self.transitionListeners[state.value].add_listener(EventType.BEFORE_ENTER, callback)

    def after_enter(self, state, callback):
        return self.transitionListeners[state.value].add_listener(EventType.AFTER_ENTER, callback)

    def before_leave(self, state, callback):
        return self.transitionListeners[state.value].add_listener(EventType.BEFORE_LEAVE, callback)

    def after_leave(self, state, callback):
        return self.transitionListeners[state.value].add_listener(EventType.AFTER_LEAVE, callback)

    def on_data(self, state, callback):
        return self.dataListeners[state.value].add_listener(EventType.DATA, callback)

    def forward_data(self, new_state, data):
        """
        Changes the state machine into the new state, then sends the data
        ignoring the result. This is so on `onData` calls we can just
        short-circuit the execution using: `return stateMachine.forwardData(..)`

        @param new_state The state to transition into.
        @param data The data to send.
        """
        self.send_data(new_state, data)

        return None

    def send_state_data(self, new_state, data):
        """
        Sends the data into the state machine, to be processed by listeners
        registered with `onData`.
        @param new_state
        @param data The data to send.
        """
        self._ensure_state_machine_initialized()
        self.changeState(new_state, data)

        target_state = self.dataListeners[self._currentState].fire(EventType.DATA, data)

        if target_state:
            return self.changeState(target_state, data)

        return self._currentState

    def send_data(self, data):
        """
        Transitions first the state machine into the new state, then it
        will send the data into the state machine.
        @param newState
        @param data
        """
        self._ensure_state_machine_initialized()
        target_state = self.dataListeners[self._currentState.value].fire(EventType.DATA, data)

        if target_state:
            return self.changeState(target_state, data)

        return self._currentState


class EventType(Enum):
    BEFORE_ENTER = 'before-enter'
    BEFORE_LEAVE = 'before-leave'
    AFTER_LEAVE = 'after-leave'
    AFTER_ENTER = 'after-enter'
    DATA = 'data'


class EventListenerRegistration(object):
    def __init__(self, event_listener, callback_id):
        self._event_listener = event_listener
        self._callback_id = callback_id

    def detach(self):
        self._event_listener.eventListeners.pop(self._callback_id)


class EventListener(object):
    def __init__(self):
        self.registered = dict()

    def add_listener(self, event_name, callback):
        event_listeners = self.registered.get(event_name.value)

        if not event_listeners:
            event_listeners = self.registered[event_name.value] = dict()

        callback_id = uuid.uuid4()
        event_listeners[callback_id] = callback

        return EventListenerRegistration(self, callback_id)

    def fire(self, event_type, ev):
        result = None

        if not self.registered.get(event_type.value):
            return

        listeners = self.registered[event_type.value]

        for callback in listeners.values():
            try:
                potential_result = callback.__call__(ev)

                if potential_result and result:
                    raise XyzStateException("Data is already returned")

                result = potential_result
            except Exception as e:
                print e
                if isinstance(e, XyzStateException):
                    raise e

        return result