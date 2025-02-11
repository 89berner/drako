from unittest import TestCase

import lib.Training.Trainer.Hackthebox as Hackthebox

import json
import lib.Common.Utils.Log as Log

class TestHTBVIP(TestCase):
    # Called when the whole class starts
    @classmethod
    def setUpClass(cls):
        Log.initialize_log("2")
        cls.client = Hackthebox.HTBVIP()

    # set when the whole class is destroyed
    @classmethod
    def tearDownClass(cls) -> None:
        Log.close_log()

    # Things that need to be setup on every test
    def setUp(self):
        pass
        # self.widget = Widget('The widget')

    # After the test method finished
    def tearDown(self):
        pass
        # self.widget.dispose()

    def test_connection_status(self):
        result = self.client.connection_status()
        self.assertEqual(result['success'], '1')

    def test_get_difficulties_map(self):
        result = self.client.get_difficulties_map()
        self.assertTrue(len(result) > 0)

    def test_get_machines(self):
        machines = self.client.get_machines()
        self.assertTrue(len(machines) > 0)

    def test_get_assigned_machines(self):
        # First we check if we have any assigned machines
        assigned_machines = self.client.get_assigned_machines()
        self.assertTrue(len(assigned_machines) > 0)

        # TODO: FIGURE OUT HOW TO TEST HACKTHEBOX SINCE IT CAN BREAK ON GOING TRAININGS, MAYBE IGNORE IF ONGOING TRAINING?
        # We have to remove this or this might break on going things assigned, we need a test environment..
        # if len(assigned_machines) > 0:
        #     print(f"test_get_assigned_machines: {assigned_machines}")
        #     # Remove the machine first
        #     for machine in assigned_machines:
        #         print(f"test_get_assigned_machines: {machine}")
        #         machine_id = machine['id']
        #         print(f"test_get_assigned_machines: Removing machine {machine_id}")
        #         self.client.remove_machine(machine_id)
        #         # print(f"Removed machine {machine_id} will wait 60 seconds")
        #         # time.sleep(60)
        #
        #     assigned_machines = self.client.get_assigned_machines()

        # Lets ensure there are non assigned machines at this point
        # self.assertEqual(len(assigned_machines), 0)

        # Now lets assign an available machine
        available_machines = self.client.get_available_machines()

        # Lets ensure there is at least 1 available machine
        self.assertTrue(len(available_machines) > 0)

        # machine_to_assign = available_machines[0]
        # response = self.client.assign_machine(machine_to_assign['id'])
        # print(response)

        # assigned_machines = self.client.get_assigned_machines()
        # self.assertEqual(len(assigned_machines), 1)

        # assigned_machine = assigned_machines[0]
        # self.assertEqual(assigned_machine['id'], machine_to_assign['id'])

    def test_get_assigned_machines_map(self):
        assigned_machines_map = self.client.get_assigned_machines_map()
        print(f"test_get_assigned_machines_map: {assigned_machines_map}")

        self.assertTrue(len(assigned_machines_map) > 0)

    def test_get_machine(self):
        machines = self.client._get_machines()
        # print(f"test_get_machine: {machines}")
        machine_id = machines[0]['id']
        # print(f"test_get_machine: {machines[0]}")

        machine = self.client.get_machine(machine_id)
        # print(f"test_get_machine: {machine}")
        self.assertTrue(machine_id, machine['id'])

    # def test_remove_machine(self):
    #     self.fail()
    #
    # def test_assign_machine(self):
    #     self.fail()
    #
    # def test_reset_machine(self):
    #     self.fail()
