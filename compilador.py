# compilador.py

from dataclasses import dataclass
import sys

filename = sys.argv[1]

@dataclass
class Instruction:
    name: str
    n_args: int
    arg_types: str
    format: str
    opcode: int
    funct: int
    real_function: None

class Compiler:
    def __init__(self, filename):
        with open(filename) as f:
            self.content = f.read()
        
        self.tokens = self.content.replace(',', ' ').replace('\n', ' ').split()

        self.instructions = dict()
        self.current_instruction = 0
        self.current_token = 0
        self.labels = dict()
        self.compiled = [0 for i in range(256)]
        self.to_resolve = []

    def compile(self):
        while self.current_token < len(self.tokens):
            self.next_token()
        
        for on_resolved, ins_num, label in self.to_resolve:
            if label.isdigit():
                real_addr = int(label)
            else:
                real_addr = self.labels[label]
            on_resolved(ins_num, real_addr)
        
        if self.compiled[0xff] == 0:
            self.compiled[0xff] = 0x380ff

        print('v2.0 raw', end='')
        
        z_len = 0
        p = 0
        for i, ins in enumerate(self.compiled):
            if ins == 0:
                z_len += 1
            if z_len >= 1 and ins != 0:
                print(f'{z_len}*0', end=' ')
                z_len = 0
                p += 1
            if p % 8 == 0:
                print()
            if ins != 0:
                print(hex(ins)[2:], end=' ')
                p += 1
        
        if z_len >= 1:
            print(f'{z_len}*0')

    def next_token(self):
        token = self.get_next_token()
        if self.is_label(token):
            self.labels[token.split(':')[0].strip()] = self.current_instruction
        else:
            self.parse_instruction(token)
    
    def get_next_token(self):
        self.current_token += 1
        return self.tokens[self.current_token - 1]
    
    def is_label(self, token):
        return token[-1] == ':'

    def parse_instruction(self, ins_name):
        ins = self.instructions[ins_name.lower()]
        raw_args = [self.get_next_token() for _ in range(ins.n_args)]
        args = [self.parse_arg(arg, t) for arg, t in zip(raw_args, ins.arg_types)]
        ins.real_function(self, *args)
        self.current_instruction += 1
    
    def parse_arg(self, arg, t):
        if t == 'R':
            return int(arg[1])
        elif t == 'I':
            return int(arg)
        elif t == 'O':
            reg = self.parse_arg(arg[:2], 'R')
            off = self.parse_arg(arg[2:].replace('(', '').replace(')', ''), 'I')
            return reg, off
        elif t == 'A':
            return arg
    
    def emit(self, ins, at=None):
        if at is None:
            at = self.current_instruction
        self.compiled[at] = ins
    
    def pack_ins_r(self, opcode, function, rd, rs, rt=0, shamt=0):
        return (opcode << 15) | (rs << 12) | (rt << 9) | (rd << 6) | (shamt << 3) | function
    
    def pack_ins_i(self, opcode, rs, rt, imm):
        return (opcode << 15) | (rs << 12) | (rt << 9) | imm
    
    def pack_ins_j(self, opcode, addr):
        return (opcode << 15) | addr
    
    def resolve_later(self, label, on_resolved):
        self.to_resolve.append((on_resolved, self.current_instruction, label))

    def instruction(self, name, n_args, arg_types, format, opcode, funct=0b000):
        def deco(f):
            self.instructions[name.lower()] = Instruction(name, n_args, arg_types, format, opcode, funct, f)
            return f
        return deco

comp = Compiler(filename)

@comp.instruction('add', 3, 'RRR', 'R', 0b000, 0b000)
def ins_add(comp, rd, rs, rt):
    comp.emit(comp.pack_ins_r(0b000, 0b000, rd, rs, rt))

@comp.instruction('sub', 3, 'RRR', 'R', 0b000, 0b001)
def ins_sub(comp, rd, rs, rt):
    comp.emit(comp.pack_ins_r(0b000, 0b001, rd, rs, rt))

@comp.instruction('mult', 3, 'RRR', 'R', 0b000, 0b010)
def ins_mult(comp, rd, rs, rt):
    comp.emit(comp.pack_ins_r(0b000, 0b010, rd, rs, rt))

@comp.instruction('div', 3, 'RRR', 'R', 0b000, 0b011)
def ins_div(comp, rd, rs, rt):
    comp.emit(comp.pack_ins_r(0b000, 0b011, rd, rs, rt))

@comp.instruction('not', 2, 'RR', 'R', 0b000, 0b100)
def ins_not(comp, rd, rs):
    comp.emit(comp.pack_ins_r(0b000, 0b100, rd, rs))

@comp.instruction('slt', 3, 'RRR', 'R', 0b000, 0b101)
def ins_slt(comp, rd, rs, rt):
    comp.emit(comp.pack_ins_r(0b000, 0b101, rd, rs, rt))

@comp.instruction('sll', 3, 'RRI', 'R', 0b000, 0b110)
def ins_sll(comp, rd, rs, n):
    comp.emit(comp.pack_ins_r(0b000, 0b110, rd, rs, shamt=n))

@comp.instruction('srl', 3, 'RRI', 'R', 0b000, 0b111)
def ins_srl(comp, rd, rs, n):
    comp.emit(comp.pack_ins_r(0b000, 0b111, rd, rs, shamt=n))

@comp.instruction('lw', 2, 'RO', 'I', 0b001)
def ins_lw(comp, rt, off):
    rs, n = off
    comp.emit(comp.pack_ins_i(0b001, rs, rt, n))

@comp.instruction('sw', 2, 'RO', 'I', 0b010)
def ins_sw(comp, rt, off):
    rs, n = off
    comp.emit(comp.pack_ins_i(0b010, rs, rt, n))

@comp.instruction('beq', 3, 'RRA', 'I', 0b011)
def ins_beq(comp, rt, rs, addr):
    def on_resolved(ins_num, real_address):
        comp.emit(comp.pack_ins_i(0b011, rs, rt, real_address), at=ins_num)
    comp.resolve_later(addr, on_resolved)

@comp.instruction('addi', 3, 'RRI', 'I', 0b100)
def ins_addi(comp, rt, rs, n):
    comp.emit(comp.pack_ins_i(0b100, rs, rt, n))

@comp.instruction('jmp', 1, 'A', 'J', 0b111)
def ins_jmp(comp, addr):
    def on_resolved(ins_num, real_address):
        comp.emit(comp.pack_ins_j(0b111, real_address), at=ins_num)
    comp.resolve_later(addr, on_resolved)

comp.compile()
