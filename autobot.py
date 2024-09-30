import re
import os
import time
from colorama import Fore as cfo
from typing import List

GRN = cfo.GREEN
RED = cfo.RED
WHT = cfo.RESET
CYN = cfo.CYAN
MGT = cfo.MAGENTA
YLW = cfo.YELLOW
GRY = cfo.WHITE
BLE = cfo.BLUE
LMG = cfo.LIGHTMAGENTA_EX

def singleton(cls):
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance

class StatusCode:
    Running = GRN+'[ RUN      ]'+WHT+' {}'
    Success = GRN+'[ .     OK ]'+WHT+' {} ({})'
    Failed  = RED+'[  FAILED  ]'+WHT+' {} ({})'
    Error   = RED+'[ .  ERROR ]'+WHT+' {}'
    Print   = GRN+'[          ]'+WHT+' {} ({})'
    Debug   = GRN+'[----------]'+WHT+' {} ({})'
    EnvMsg  = GRN+'[==========]'+WHT+' {}'

def format_time(value: float) -> str:
    if value >= 1.0:
        return f"{value:.2f} s"
    else:
        milliseconds = value * 1000
        return f"{milliseconds:.2f} ms"

@singleton
class TimeCounter:

    total_call_count = 0
    
    def __init__(self):
        self.reset()
        self.accumulated = 0

    def reset(self) -> None:
        self.last_measure = time.time()

    def time(self) -> str:
        temp = self.last_measure
        self.reset()
        diff = self.last_measure - temp
        self.accumulated += diff
        return format_time(diff)

    def total(self) -> None:
        TimeCounter().total_call_count += 1
        print(StatusCode.Debug.format(f"{YLW}{TimeCounter().total_call_count}{WHT} Total time", format_time(self.accumulated)))
        self.accumulated = 0

def get_error(obj: object) -> str:
    attr = 'error'
    if not hasattr(obj, attr) and not isinstance(getattr(obj, attr), str):
        raise AttributeError(f"Atribute [error] not found in {type(obj).__name__}")
    
    return obj.error

def stprint(msg: str) -> None:
    print(StatusCode.Print.format(msg, TimeCounter().time()))

def stdebug(msg: str) -> None:
    print(StatusCode.Debug.format(msg, TimeCounter().time()))

def stenvmsg(msg: str) -> None:
    TimeCounter().reset()
    print(StatusCode.EnvMsg.format(msg))

def procedure_status(msg: str, obj: object, method_name: str) -> str:

    print(StatusCode.Running.format(f"Running {LMG}{(type(obj).__name__)}{YLW}.{BLE}{method_name}{WHT}()"))
        
    method = getattr(obj, method_name)

    TimeCounter().reset()
    value = method()
    exec_time = TimeCounter().time()
    
    if not value:
        print(StatusCode.Failed.format(msg, exec_time))
        print(StatusCode.Error.format(get_error(obj)))
    else:
        print(StatusCode.Success.format(msg, exec_time))

    return value

class ParserToken:
    class Keyword:
        def __init__(self, value: str) -> None:
            self.value = value

        def __repr__(self) -> str:
            return f"{CYN}KeyId{WHT}[{MGT}{repr(self.value)[1:-1]}{WHT}]"
        
        def __str__(self):
            return self.value
            

    def __init__(self, id: str, value: str='', line: int=0, col: int=0) -> None:
        self.id = id
        self.line = line
        self.col = col
        if id.__contains__('Integer'):
            self.value = int(value)
        elif id.__contains__('Float'):
            self.value = float(value)
        elif id.__contains__('String'):
            self.value = value[1:-1]
        else:
            self.value = self.Keyword(value)

    def __eq__(self, other: object):
        if isinstance(other, ParserToken):
            return self.id == other.id
        if isinstance(other, str):
            return self.id == other
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{CYN}TOKEN{WHT}<{MGT}{self.id}{WHT}[{YLW}{self.line}:{self.col}{WHT}], {MGT}{type(self.value).__name__}{WHT}({self.value})>"

class AutobotLexer:
    def __init__(self, code: str) -> None:
        self.code = code + '\n'
        self.tokens: List[ParserToken] = []
        self.current_position = 0
        self.error = ''

    def next_jumpline(self) -> List[ParserToken]:
        try:
            found_at = self.tokens.index('NEWLINE', self.pos)
        except ValueError:
            chunk = self.tokens[self.pos:]
            self.pos = len(self.tokens)
            return chunk
        
        chunk = self.tokens[self.pos:self.pos+found_at]
        self.pos = found_at + 1
        return chunk
    
    def eof(self) -> bool:
        return self.pos >= len(self.tokens)

    def tokenize(self) -> bool:
        patterns = {
            'ExecuteBinary': r'START',
            'LeftClickOnImage': r'CLICK',
            'WriteText': r'INPUT',
            'PressKeys': r'PRESS',
            'DoWhileOnDataframe': r'DO',
            'IfImageOnScreenDo': r'IFIOS',
            'IterateDataframe': r'ITERDF',
            'LiteralFloat': r'\d+\.\d+',         # Flotantes
            'LiteralInteger': r'\b\d+\b',        # Enteros (evitar puntos decimales)
            'LiteralString': r'\'[^\']*\'',      # Cadenas entre comillas simples
            'GetColumnBy': r'\$',              # Token '#'
            'WaitScreenUpdate': r'\!',              # Token '!'
            'StoredKeyname': r'[a-zA-Z_][a-zA-Z0-9_]*',  # Keys
            'NEWLINE': r'\n',
            'ONECOMMENT':  r'--([\s\S]*?)\n',
            'MULTICOMMENT': r'-<[\s\S]*?(>-|\n?$)',
            'SKIP': r'[ \t]+',            # Espacios y tabulaciones
        }

        line = 1
        offset = 0
        while self.current_position < len(self.code):
            match = None
            for token_type, pattern in patterns.items():
                regex = re.compile(pattern)
                match = regex.match(self.code, self.current_position)
                if match:
                    text = match.group(0)
                    forward = len(text)

                    if token_type == 'ONECOMMENT':
                        forward -= 1
                        
                    if token_type not in ['SKIP', 'ONECOMMENT', 'MULTICOMMENT']:
                        if not (token_type == 'NEWLINE' and 
                                (not self.tokens or self.tokens[-1].id == 'NEWLINE')):
                            self.tokens.append(ParserToken(token_type, text, line, offset))
                    
                    if token_type == 'NEWLINE':
                        line += 1
                        offset = 0

                    else:
                        offset += forward

                    self.current_position += forward
                    break

            if not match:
                self.error = f"BadToken[at({YLW}{line}:{offset}{WHT}), {MGT}char{WHT}({self.code[self.current_position]})]"
                return False

        count = len(self.tokens)
        if count > 0:
            self.pos = 0
            stprint(f"Tokens count {count}")
            return True
        
        self.error = 'EmptyCode'
        return False
    
class AutobotCommand:

    COMMANDS = {
        'ExecuteBinary': {'expected': ['LiteralString', 'WaitScreenUpdate'], 
                          'return': 'NoneType',
                          'function': lambda x: x},
        'LeftClickOnImage': {'expected': ['LiteralString', 'WaitScreenUpdate'],
                             'return': 'NoneType',
                             'function': lambda x: x},
        'WriteText': {'expected': ['LiteralString|GetColumnBy'],
                      'return': 'NoneType',
                      'function': lambda x: x},
        'PressKeys': {'expected': ['StoredKeyname'],
                      'return': 'NoneType',
                      'function': lambda x: x},
        'DoWhileOnDataframe': {'expected': ['LiteralString'],
                               'return': 'NoneType',
                               'function': lambda x: x},
        'IfImageOnScreenDo': {'expected': ['LiteralString', 'ExecuteBinary|LeftClickOnImage|WriteText|PressKeys'],
                              'return': 'NoneType',
                              'function': lambda x: x},
        'IterateDataframe': {'expected': ['StoredKeyname', 'LiteralInteger'],
                             'return': 'NoneType',
                             'function': lambda x, y: (x, y)},
        'GetColumnBy': {'expected': ['LiteralInteger|LiteralString'],
                        'return': 'str',
                        'function': lambda x: 'STRING DE PRUEBA'},
        'WaitScreenUpdate': {'expected': ['LiteralInteger|LiteralFloat'],
                             'return': 'NoneType',
                             'function': lambda x: x}
    }

    def __init__(self, tokens: List[ParserToken]) -> None:
        self.token_buffer = tokens
        self.command = self.token_buffer.pop(0)
        self.argv: List[List[ParserToken|AutobotCommand]] = []
        self.result: ParserToken = None
        self.error = ''

    def consume(self) -> bool:
        def is_nonterminal(x):
            return x in self.COMMANDS.keys()

        if is_nonterminal(self.command.id):
            expected = self.COMMANDS[self.command.id]['expected']
            stprint(f"Command [{MGT}{self.command.value}{WHT}] expects {YLW}{len(expected)}{WHT} parameters")
            for exp in expected:

                productions = exp.split('|')
                parsed: List[ParserToken|AutobotCommand] = []

                if not self.token_buffer:
                    self.error = f"NotEnoughTokensReceived"
                    return False
                
                for production in productions:
                    if self.token_buffer[0] == production:
                        if is_nonterminal(production):

                            try:
                                sub_command = AutobotCommand(self.token_buffer)
                            except IndexError:
                                self.error = f"NotEnoughTokensReceived"
                                return False
                            
                            procedure_status(f"Sub-command consuming tokens", sub_command, 'consume')
                            parsed.append(sub_command)
                        else:
                            parsed.append(self.token_buffer.pop(0))
                self.argv.append(parsed)

            return True
        else:
            self.error = f"{MGT}{self.command.id}{WHT} found at {YLW}{self.command.line}:{self.command.col}{WHT} position, is not a valid command"
            return False

    def execute(self) -> bool:
        parameters: List[ParserToken] = []
        function_chain: AutobotCommand = None

        for arg in self.argv:
            for rep in arg:
                if isinstance(rep, ParserToken):
                    parameters.append(rep.value)
                elif isinstance(rep, AutobotCommand):
                    if self.COMMANDS[rep.command.id]['return'] != 'NoneType':
                        status = procedure_status(f"Executing sub-command [{CYN}{rep.command.id}{WHT}]", rep, 'execute')
                        if status:
                            parameters.append(rep.result)
                        else:
                            self.error = f"Required sub-command {RED}{rep.command.value}{WHT} result failed"
                            return False
                    else:
                        function_chain = rep

        sep = f"{WHT}, {YLW}"
        
        stprint(f"Command {MGT}{self.command.value}{WHT}({YLW}{sep.join(map(str, parameters))}{WHT}) execution")
        self.result = self.COMMANDS[self.command.id]['function'](*parameters)
        
        if function_chain is not None:
            status = procedure_status(f"Executing post-command [{CYN}{function_chain.command.id}{WHT}]", function_chain, 'execute')
            
            if status:
                return True
            
            self.error = f"Required post-command {RED}{function_chain.command.value}{WHT} result failed"
            return False
        
        return True

class AutobotCode:
    def __init__(self, fn_code: str) -> None:
        self.fn = fn_code
        self.code = ''
        self.error = ''

    def read_file(self):
        if not os.path.isfile(self.fn):
            self.error = 'FileNotFound'
            return False

        with open(self.fn, 'r', encoding='utf-8') as file:
            self.code = file.read()
        return True
    
    def execute(self):
        stenvmsg('Reading and Scanning tokens')

        code_read = procedure_status(f"Code read from {self.fn}", self, 'read_file')

        self.lexer = AutobotLexer(self.code)
        scanned = procedure_status('Code scan', self.lexer, 'tokenize')

        TimeCounter().total()
        if code_read and scanned:
            stenvmsg(GRN + 'Bot ready!')

            while not self.lexer.eof():
                tokens = self.lexer.next_jumpline()
                command = AutobotCommand(tokens)
                if not procedure_status(f"Consuming tokens. Left: {YLW}{len(tokens)}{WHT} tokens", command, 'consume'):
                    TimeCounter().total()
                    break
                procedure_status('Processing command', command, 'execute')
                TimeCounter().total()
        else:
            stenvmsg(RED + 'Unable to run bot')
        stenvmsg(GRY + 'EOF reached. Shutting down!')


if __name__ == '__main__':

    autobot = AutobotCode('steps.txt')
    autobot.execute()
