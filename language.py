class Language:
    _table = {}

    def __init__(self, name, file_ext, compile_cmd, execute_cmd):
        self.name = name
        self.file_ext = file_ext
        self.compile_cmd = compile_cmd
        self.execute_cmd = execute_cmd

        Language._table[name] = self

    def get_compile_cmd(self, code_file):
        return self.compile_cmd.format(code_file).split()

    def get_execute_cmd(self):
        return self.execute_cmd.split()

    @staticmethod
    def get(name):
        return Language._table.get(name)


Language('cpp', '.cpp', 'g++ {} -o program', './program')
