import unittest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.graph.utils import filter_supervisor_history

class TestSupervisorFilter(unittest.TestCase):
    def test_filter_excludes_tools_and_other_agents(self):
        # Create a mixed history
        messages = [
            HumanMessage(content="Hi"),
            AIMessage(content="Thinking...", name="Supervisor"),
            AIMessage(content="Checking email", name="email_agent"),
            ToolMessage(content="Email content", tool_call_id="1", name="email_tool"),
            AIMessage(content="Done checking", name="email_agent"),
            AIMessage(content="Summary: Checked emails", name="sub_agent_task_summary"),
            AIMessage(content="Here is the summary.", name="Supervisor"),
            HumanMessage(content="Thanks")
        ]
        
        filtered = filter_supervisor_history(messages, limit=10)
        
        # Expected: Human, Supervisor, Task Summary are kept. Others dropped.
        expected_contents = [
            "Hi",
            "Thinking...",
            "Summary: Checked emails",
            "Here is the summary.",
            "Thanks"
        ]
        
        self.assertEqual(len(filtered), 5)
        for i, msg in enumerate(filtered):
            self.assertEqual(msg.content, expected_contents[i])

    def test_limit_logic(self):
        # Create 30 messages
        messages = [HumanMessage(content=f"Msg {i}") for i in range(30)]
        
        filtered = filter_supervisor_history(messages, limit=20)
        
        self.assertEqual(len(filtered), 20)
        self.assertEqual(filtered[0].content, "Msg 10")
        self.assertEqual(filtered[-1].content, "Msg 29")

if __name__ == "__main__":
    unittest.main()
