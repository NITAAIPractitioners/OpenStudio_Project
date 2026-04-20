import ast
with open(r'c:\Users\me.com\Documents\engery\OpenStudio_Project\bugfix_working\aswani_model\run_all_validations.py') as f:
    src = f.read()
ast.parse(src)
print('PARSE OK')

for name in ['Aswani-VAV', 'Ideal', 'Not-Ideal']:
    print(f'  {name}: present={repr(name) in src}')

stale = ['run_20260416_162119', 'run_20260417_151213', 'Ideal_Loads', 'VAV_Reheat']
for s in stale:
    print(f'  stale "{s}": present={s in src}')

with open(r'c:\Users\me.com\Documents\engery\OpenStudio_Project\original_frozen\aswani_model\run_all_validations.py') as f:
    orig = f.read()
print(f'  original has old keys: {"Ideal_Loads" in orig}')
print(f'  original missing Not-Ideal: {"Not-Ideal" not in orig}')
