import pathlib
code = pathlib.Path('bookhara_new.py').read_text(encoding='utf-8')
pathlib.Path('apps/integrations/adapters/bookhara.py').write_text(code, encoding='utf-8')
print('OK:', len(code))
