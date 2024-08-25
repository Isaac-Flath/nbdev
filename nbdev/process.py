# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/api/03_process.ipynb.

# %% auto 0
__all__ = ['langs', 'nb_lang', 'first_code_ln', 'extract_directives', 'opt_set', 'instantiate', 'NBProcessor', 'Processor']

# %% ../nbs/api/03_process.ipynb
from .config import *
from .maker import *
from .imports import *

from execnb.nbio import *
from fastcore.script import *
from fastcore.imports import *

from collections import defaultdict

# %% ../nbs/api/03_process.ipynb
# from https://github.com/quarto-dev/quarto-cli/blob/main/src/resources/jupyter/notebook.py
langs = defaultdict(
    lambda: '#',  r = "#", python = "#", julia = "#", scala = "//", matlab = "%", csharp = "//", fsharp = "//",
    c = ["/*","*/"], css = ["/*","*/"], sas = ["*",";"], powershell = "#", bash = "#", sql = "--", mysql = "--", psql = "--",
    lua = "--", cpp = "//", cc = "//", stan = "#", octave = "#", fortran = "!", fortran95 = "!", awk = "#", gawk = "#", stata = "*",
    java = "//", groovy = "//", sed = "#", perl = "#", ruby = "#", tikz = "%", javascript = "//", js = "//", d3 = "//", node = "//",
    sass = "//", coffee = "#", go = "//", asy = "//", haskell = "--", dot = "//", apl = "⍝")

# %% ../nbs/api/03_process.ipynb
def nb_lang(nb): return nested_attr(nb, 'metadata.kernelspec.language', 'python')

# %% ../nbs/api/03_process.ipynb
def _dir_pre(lang=None): return fr"\s*{langs[lang]}\s*\|"
def _quarto_re(lang=None): return re.compile(_dir_pre(lang) + r'\s*[\w|-]+\s*:')

# %% ../nbs/api/03_process.ipynb
def _directive(s, lang='python'):
    s = re.sub('^'+_dir_pre(lang), f"{langs[lang]}|", s)
    if s.strip().endswith(':'): s = s.replace(':', '') # You can append colon at the end to be Quarto compliant.  Ex: #|hide:
    if ':' in s: s = s.replace(':', ': ')
    s = (s.strip()[2:]).strip().split()
    if not s: return None
    direc,*args = s
    return direc,args

# %% ../nbs/api/03_process.ipynb
def _norm_quarto(s, lang='python'):
    "normalize quarto directives so they have a space after the colon"
    m = _quarto_re(lang).match(s)
    return m.group(0) + ' ' + _quarto_re(lang).sub('', s).lstrip() if m else s

# %% ../nbs/api/03_process.ipynb
_cell_mgc = re.compile(r"^\s*%%\w+")

def first_code_ln(code_list, re_pattern=None, lang='python'):
    "get first line number where code occurs, where `code_list` is a list of code"
    if re_pattern is None: re_pattern = _dir_pre(lang)
    return first(i for i,o in enumerate(code_list) if o.strip() != '' and not re.match(re_pattern, o) and not _cell_mgc.match(o))

# %% ../nbs/api/03_process.ipynb
def _partition_cell(cell, lang):
    if not cell.source: return [],[]
    lines = cell.source.splitlines(True)
    first_code = first_code_ln(lines, lang=lang)
    return lines[:first_code],lines[first_code:]

# %% ../nbs/api/03_process.ipynb
def extract_directives(cell, remove=True, lang='python'):
    "Take leading comment directives from lines of code in `ss`, remove `#|`, and split"
    dirs,code = _partition_cell(cell, lang)
    if not dirs: return {}
    if remove:
        # Leave Quarto directives and cell magic in place for later processing
        cell['source'] = ''.join([_norm_quarto(o, lang) for o in dirs if _quarto_re(lang).match(o) or _cell_mgc.match(o)] + code)
    return dict(L(_directive(s, lang) for s in dirs).filter())

# %% ../nbs/api/03_process.ipynb
def opt_set(var, newval):
    "newval if newval else var"
    return newval if newval else var

# %% ../nbs/api/03_process.ipynb
def instantiate(x, **kwargs):
    "Instantiate `x` if it's a type"
    return x(**kwargs) if isinstance(x,type) else x

def _mk_procs(procs, nb): return L(procs).map(instantiate, nb=nb)

# %% ../nbs/api/03_process.ipynb
def _is_direc(f): return getattr(f, '__name__', '-')[-1]=='_'

# %% ../nbs/api/03_process.ipynb
class NBProcessor:
    "Process cells and nbdev comments in a notebook"
    def __init__(self, path=None, procs=None, nb=None, debug=False, rm_directives=True, process=False):
        self.nb = read_nb(path) if nb is None else nb
        self.lang = nb_lang(self.nb)
        for cell in self.nb.cells: cell.directives_ = extract_directives(cell, remove=rm_directives, lang=self.lang)
        self.procs = _mk_procs(procs, nb=self.nb)
        self.debug,self.rm_directives = debug,rm_directives
        if process: self.process()

    def _process_cell(self, proc, cell):
        if not hasattr(cell,'source'): return
        if cell.cell_type=='code' and cell.directives_:
            # Option 1: `proc` is directive name with `_` suffix
            f = getattr(proc, '__name__', '-').rstrip('_')
            if f in cell.directives_: self._process_comment(proc, cell, f)
            
            # Option 2: `proc` contains a method named `_{directive}_`
            for cmd in cell.directives_:
                f = getattr(proc, f'_{cmd}_', None)
                if f: self._process_comment(f, cell, cmd)
        if callable(proc) and not _is_direc(proc): cell = opt_set(cell, proc(cell))

    def _process_comment(self, proc, cell, cmd):
        args = cell.directives_[cmd]
        if self.debug: print(cmd, args, proc)
        return proc(cell, *args)
        
    def _proc(self, proc):
        if hasattr(proc,'begin'): proc.begin()
        for cell in self.nb.cells: self._process_cell(proc, cell)
        if hasattr(proc,'end'): proc.end()
        self.nb.cells = [c for c in self.nb.cells if c and getattr(c,'source',None) is not None]
        for i,cell in enumerate(self.nb.cells): cell.idx_ = i

    def process(self):
        "Process all cells with all processors"
        for proc in self.procs: self._proc(proc)

# %% ../nbs/api/03_process.ipynb
class Processor:
    "Base class for processors"
    def __init__(self, nb): self.nb = nb
    def cell(self, cell): pass
    def __call__(self, cell): return self.cell(cell)
