import unittest

from smpy.XyzStateMachine import XyzStateMachine, XyzState, XyzStateChangeEvent


class TestXyzStateMachine(unittest.TestCase):
    def setup(self):
        self.expected = 0
        self.stateMachine = None

    def test_initial_change_event(self):
        stateMachine = XyzStateMachine()

        def after_enter(ev: XyzStateChangeEvent):
            self.assertTrue(ev.previous_state is None)

        stateMachine.after_enter(XyzState.DEFAULT, after_enter)
        stateMachine.changeState(XyzState.RUNNING)

    def test_state_machine(self):
        stateMachine = XyzStateMachine()
        self.expected = 0

        def before_enter(ev):
            self.assertEqual(0, self.expected)
            self.expected += 1

        def after_enter(ev):
            self.assertEqual(1, self.expected)
            self.expected += 2

        def before_leave(ev):
            self.assertEqual(3, self.expected)
            self.expected += 3

        def after_leave(ev):
            self.assertEqual(6, self.expected)
            self.expected += 4

        stateMachine.before_enter(XyzState.RUNNING, before_enter)
        stateMachine.after_enter(XyzState.RUNNING, after_enter)
        stateMachine.before_leave(XyzState.RUNNING, before_leave)
        stateMachine.after_leave(XyzState.RUNNING, after_leave)

        stateMachine.changeState(XyzState.RUNNING)
        self.assertEqual(3, self.expected)

        stateMachine.changeState(XyzState.STOPPED)
        self.assertEqual(10, self.expected)

    def test_failed_listener_doesnt_fail_state_machine(self):
        stateMachine = XyzStateMachine()

        self.expected = 0

        def before_enter(ev):
            self.assertEqual(0, self.expected)
            self.expected += 1

        def after_enter(ev):
            raise Exception("test error")

        stateMachine.before_enter(XyzState.RUNNING, before_enter)
        stateMachine.after_enter(XyzState.RUNNING, after_enter)

        stateMachine.changeState(XyzState.RUNNING)
        self.assertEqual(1, self.expected)

    def test_cancelling_events_stops_transitions(self):
        stateMachine = XyzStateMachine()
        self.expected = 0

        def before_enter(ev):
            self.assertEqual(0, self.expected)
            self.expected += 1

            ev.cancel()

        def after_enter(ev):
            raise Exception("Should not enter, since the event was cancelled")

        stateMachine.before_enter(XyzState.RUNNING, before_enter)
        stateMachine.after_enter(XyzState.RUNNING, after_enter)

        self.assertEqual(XyzState.DEFAULT, stateMachine.state)
        stateMachine.changeState(XyzState.RUNNING)

        self.assertEqual(XyzState.DEFAULT, stateMachine.state)
        self.assertEqual(1, self.expected)

    def test_performance(self):
        stateMachine = XyzStateMachine()
        self.expected = 0

        def before_enter(ev):
            self.expected += 1

        def after_enter(ev):
            self.expected += 2

        def before_leave(ev):
            self.expected += 3

        def after_leave(ev):
            self.expected += 4

        stateMachine.before_enter(XyzState.RUNNING, before_enter)
        stateMachine.after_enter(XyzState.RUNNING, after_enter)

        stateMachine.before_leave(XyzState.RUNNING, before_leave)
        stateMachine.after_leave(XyzState.RUNNING, after_leave)

        for i in range(100000):
            stateMachine.changeState(XyzState.RUNNING)
            stateMachine.changeState(XyzState.DEFAULT)

        self.assertEqual(1000000, self.expected)

    def test_initial_state_test(self):
        stateMachine = XyzStateMachine(XyzState.DEFAULT)
        self.expected = 0

        def before_enter(ev):
            self.expected += 1

        def before_leave(ev):
            self.expected += 2

        stateMachine.before_enter(XyzState.DEFAULT, before_enter)
        stateMachine.before_leave(XyzState.DEFAULT, before_leave)

        self.assertEqual(0, self.expected)
        stateMachine.changeState(XyzState.RUNNING)
        self.assertEqual(3, self.expected)

    def test_data_gets_passed_into_the_event(self):
        stateMachine = XyzStateMachine(XyzState.DEFAULT)
        self.expected = 0

        def before_leave(ev):
            self.expected += 1 + ev.data

        stateMachine.before_leave(XyzState.DEFAULT, before_leave)

        self.assertEqual(0, self.expected)
        stateMachine.changeState(XyzState.RUNNING, 3)
        self.assertEqual(4, self.expected)

    def test_changing_the_state_in_an_after_listener(self):
        self.stateMachine = XyzStateMachine(XyzState.DEFAULT)
        self.expected = 0

        def after_enter_change_state(ev):
            self.stateMachine.changeState(XyzState.STOPPED)

        def after_enter(ev):
            self.expected += 1

        self.stateMachine.after_enter(XyzState.RUNNING, after_enter_change_state)
        self.stateMachine.after_enter(XyzState.RUNNING, after_enter)

        self.assertEqual(XyzState.DEFAULT, self.stateMachine.state)
        self.stateMachine.changeState(XyzState.RUNNING)
        self.assertEqual(XyzState.STOPPED, self.stateMachine.state)
        self.assertEqual(1, self.expected)

    def test_changing_the_state_in_an_before_listener_is_not_allowed(self):
        self.stateMachine = XyzStateMachine(XyzState.DEFAULT)

        def before_enter(ev):
            self.stateMachine.changeState(XyzState.STOPPED)

        self.stateMachine.before_enter(XyzState.RUNNING, before_enter)

        self.assertEqual(XyzState.DEFAULT, self.stateMachine.state)

        with self.assertRaises(Exception):
            self.stateMachine.changeState(XyzState.RUNNING)

    def test_data_routing(self):
        stateMachine = XyzStateMachine(XyzState.DEFAULT)

        self.data = ""

        def on_default_data(name: str) -> None:
            self.data += "DEFAULT:" + name + ","

        def on_running_data(name: str) -> XyzState:
            self.data += "RUNNING:" + name + ","
            return XyzState.STOPPED

        stateMachine.on_data(XyzState.DEFAULT, on_default_data)
        stateMachine.on_data(XyzState.RUNNING, on_running_data)

        stateMachine.send_data("default")
        stateMachine.send_data("default")
        stateMachine.run()
        stateMachine.send_data("running")
        stateMachine.send_data("running")

        self.assertEqual("DEFAULT:default,DEFAULT:default,RUNNING:running,", self.data)
        self.assertEqual(XyzState.STOPPED, stateMachine.state)

    def test_invalid_transitions_should_not_work(self):
        stateMachine = XyzStateMachine(XyzState.STOPPED)
        newState = stateMachine.changeState(XyzState.RUNNING)

        self.assertEqual(XyzState.STOPPED, newState)

    def test_initializations_on_transitions(self):
        stateMachine = XyzStateMachine(XyzState.DEFAULT)
        stateMachine.transition("run")

        self.assertEqual(XyzState.RUNNING, stateMachine.state)

    def test_resending_data(self):
        self.stateMachine = XyzStateMachine()
        self.expected = 0

        def on_default_data(data):
            self.stateMachine.send_state_data(XyzState.RUNNING, data + 2)

        def on_running_data(data):
            self.stateMachine.send_state_data(XyzState.STOPPED, data + 3)

        def on_stopped_data(data):
            self.expected = data

        self.stateMachine.on_data(XyzState.DEFAULT, on_default_data)
        self.stateMachine.on_data(XyzState.RUNNING, on_running_data)
        self.stateMachine.on_data(XyzState.STOPPED, on_stopped_data)

        state = self.stateMachine.send_data(1)

        self.assertEqual(XyzState.STOPPED, state)
        self.assertEqual(6, self.expected)
        self.assertEqual(XyzState.STOPPED, self.stateMachine.state)


if __name__ == '__main__':
    unittest.main()
