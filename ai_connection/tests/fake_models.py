import base64

from odoo import fields, models

from odoo.addons.ai_connection.client import AiConnectionClient

# The clients the connection built, most recent last. A test reads the
# last one to see what the connection actually sent; the context is not a
# place to hand a mutable list around, and _run_ai returns no handle on
# the client it used.
CLIENTS = []


def _remember(client):
    CLIENTS.append(client)
    return client


class AiClientDemo(AiConnectionClient):
    def __init__(self, tools):
        super().__init__()
        self.tools = tools or []
        # What the connection handed us, call by call. A test that wants
        # to know whether a tool answer made it back into the exchange has
        # no other way to look: _run_ai returns the content, never the
        # messages it sent.
        self.seen = []

    def handle_message(self, messages, **kwargs):
        self.seen.append(list(messages))
        last_message = messages[-1]
        content = last_message["content"]
        if last_message.get("files"):
            content = base64.b64decode(last_message["files"][0]["content"]).decode(
                "utf-8"
            )
        if any(tool.name == content for tool in self.tools):
            return {
                "message": {
                    "role": "assistant",
                    "content": f"This is a demo response to the prompt: {content}",
                },
                "tool_calls": [
                    {
                        "name": content,
                        "arguments": {},
                    }
                ],
            }
        return {
            "message": {
                "role": "assistant",
                "content": "This is a demo response to the prompt: " f"{content}",
            },
        }




class AiClientFailingTool(AiClientDemo):
    """Asks for a tool with an argument the tool does not accept.

    The call therefore raises inside _execute_tool, which is the case the
    connection has to survive: the model asked for something the tool
    could not do, and it must be told so rather than left waiting.
    """

    def handle_message(self, messages, **kwargs):
        self.seen.append(list(messages))
        if any(message.get("role") == "tool" for message in messages):
            return {
                "message": {
                    "role": "assistant",
                    "content": "I saw the error and stopped.",
                },
            }
        return {
            "message": {"role": "assistant", "content": "Calling the tool."},
            "tool_calls": [
                {
                    "name": self.tools[0].name if self.tools else "unknown",
                    "arguments": {"an_argument_that_does_not_exist": 1},
                    "id": "call-1",
                }
            ],
        }


class AiConnection(models.Model):
    _inherit = "ai.connection"

    kind = fields.Selection(
        selection_add=[("demo", "Demo"), ("failing_tool", "Failing tool")],
        ondelete={"demo": "cascade", "failing_tool": "cascade"},
    )

    def _get_client_demo(self, tools):
        return _remember(AiClientDemo(tools))

    def _get_client_failing_tool(self, tools):
        return _remember(AiClientFailingTool(tools))
