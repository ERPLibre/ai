# Copyright 2026 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from freezegun import freeze_time
from odoo_test_helper import FakeModelLoader

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestConnection(TransactionCase):
    def setUp(self):
        super().setUp()
        self.loader = FakeModelLoader(self.env, self.__module__)
        self.loader.backup_registry()
        from .fake_models import AiConnection

        self.loader.update_registry((AiConnection,))
        self.addCleanup(self.loader.restore_registry)

    def test_demo_connection(self):
        connection = self.env["ai.connection"].create(
            {
                "name": "Demo Connection",
                "kind": "demo",
            }
        )
        response = connection._run("Hello, AI!")
        self.assertEqual(
            response[0], "This is a demo response to the prompt: Hello, AI!"
        )
        self.assertEqual(response[3], 1)

    def test_demo_connection_with_attachment(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "test.txt",
                "datas": "SGVsbG8sIEFJIQ==",  # Base64 for "Hello, AI!"
                "mimetype": "text/plain",
            }
        )
        connection = self.env["ai.connection"].create(
            {
                "name": "Demo Connection",
                "kind": "demo",
            }
        )
        response = connection._run(attachments=attachment)
        self.assertEqual(
            response[0], "This is a demo response to the prompt: Hello, AI!"
        )
        self.assertEqual(response[3], 1)

    def test_demo_connection_with_tool(self):
        tool = self.env.ref("ai_tool.current_date")
        connection = self.env["ai.connection"].create(
            {
                "name": "Demo Connection",
                "kind": "demo",
            }
        )
        with freeze_time("2024-01-01"):
            response = connection._run("get_date", tools=tool)
        self.assertEqual(
            response[0], 'This is a demo response to the prompt: {"date": "2024-01-01"}'
        )
        self.assertEqual(response[3], 2)

    def test_demo_connection_max_iterations(self):
        tool = self.env.ref("ai_tool.current_date")
        connection = self.env["ai.connection"].create(
            {
                "name": "Demo Connection",
                "kind": "demo",
            }
        )
        with self.assertRaises(UserError):
            connection._run("get_date", tools=tool, max_iterations=1)

    def test_a_failing_tool_is_answered_and_the_loop_goes_on(self):
        """A tool that raises must still produce a role="tool" message.

        Without it the tool call stays unanswered: a provider that
        validates the exchange refuses the next iteration, so one failing
        tool takes the whole conversation down instead of letting the
        model read the error and try something else.
        """
        from .fake_models import CLIENTS

        CLIENTS.clear()
        tool = self.env.ref("ai_tool.current_date")
        connection = self.env["ai.connection"].create(
            {
                "name": "Failing Tool Connection",
                "kind": "failing_tool",
            }
        )
        response = connection._run("go", tools=tool)
        self.assertEqual(response[0], "I saw the error and stopped.")
        self.assertTrue(CLIENTS)
        second_call = CLIENTS[-1].seen[-1]
        answers = [
            message
            for message in second_call
            if message.get("role") == "tool"
        ]
        self.assertEqual(len(answers), 1)
        self.assertIn("error", answers[0]["content"])

    def test_an_unoffered_tool_does_not_raise(self):
        """tools defaults to None, and a model can name a tool anyway.

        Filtering None raises AttributeError, which reaches the caller as
        a traceback rather than as the "unknown tool" the loop already
        handles by skipping.
        """
        from .fake_models import CLIENTS

        CLIENTS.clear()
        connection = self.env["ai.connection"].create(
            {
                "name": "Failing Tool Connection",
                "kind": "failing_tool",
            }
        )
        with self.assertRaises(UserError):
            connection._run("go", max_iterations=2)
