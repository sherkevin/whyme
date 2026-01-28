"""Stub for aider.io.InputOutput."""

class InputOutput:
    def __init__(self, pretty=True, yes=False, input_history_file=None, chat_history_file=None, encoding='utf-8', dry_run=False):
        self.pretty = pretty
        self.yes = yes
        self.input_history_file = input_history_file
        self.chat_history_file = chat_history_file
        self.encoding = encoding
        self.dry_run = dry_run

    def tool_output(self, msg, log_only=False):
        print(msg)

    def get_input(self, prompt, line_editor=None):
        return input(prompt)
        
    def confirm_ask(self, question, default="y"):
        return True
