import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

from evaluator import evaluate_source


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def module(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_source(self, text):
        result, env = evaluate_source(text, source_path=self.root/'main.v')
        self.assertEqual(result, (None, None))
        return env

    def test_global_bindings_are_returned_without_return(self):
        self.module('utility.v', 'factor=2; function scale(x){return factor*x}; sqrt=native("math.sqrt",["x"])')
        env = self.run_source('m=import("utility.v"); a=m.scale(5); b=m.sqrt(9); kind=type(m)')
        self.assertEqual((env['a'],env['b'],env['kind']),(10,3,'object'))
        self.assertEqual(set(env['m']), {'factor','scale','sqrt'})

    def test_returned_object_is_the_actual_environment(self):
        self.module('state.v', 'factor=2; function scale(x){return factor*x}; function bump(){set factor=factor+1}')
        env=self.run_source('m=import("state.v"); m.factor=3; a=m.scale(5); m.bump(); b=m.factor')
        self.assertEqual((env['a'],env['b']),(15,4))
        self.assertIs(env['m'],env['m']['scale']['environment'])

    def test_module_does_not_see_caller_bindings(self):
        self.module('bad.v','result=secret')
        with self.assertRaisesRegex(ValueError,'Unknown identifier: secret'):
            self.run_source('secret=42; import("bad.v")')

    def test_repeated_imports_are_independent_and_rerun(self):
        self.module('state.v','count=0; print("loaded"); function next(){set count=count+1;return count}')
        out=io.StringIO()
        with redirect_stdout(out):
            env=self.run_source('a=import("state.v"); b=import("state.v"); x=a.next(); y=b.count')
        self.assertIsNot(env['a'],env['b'])
        self.assertEqual((env['x'],env['y']),(1,0))
        self.assertEqual(out.getvalue(),'loaded\nloaded\n')

    def test_nested_relative_imports(self):
        self.module('package/a.v','b=import("b.v"); answer=b.value')
        self.module('package/b.v','value=42')
        env=self.run_source('a=import("package/a.v"); answer=a.answer')
        self.assertEqual(env['answer'],42)

    def test_later_import_from_module_function_uses_its_file(self):
        self.module('package/a.v','function load(){return import("b.v")}')
        self.module('package/b.v','value=42')
        env=self.run_source('a=import("package/a.v"); load=a.load; b=load(); answer=b.value')
        self.assertEqual(env['answer'],42)

    def test_import_is_assignable_and_shadowable(self):
        self.module('x.v','x=1')
        env=self.run_source('load=import; m=load("x.v"); import=function(x){return x+1}; answer=import(4)')
        self.assertEqual((env['m']['x'],env['answer']),(1,5))

    def test_empty_program_returns_empty_object(self):
        self.module('empty.v','')
        env=self.run_source('m=import("empty.v"); equal=m=={}; text=string(m)')
        self.assertEqual(env['m'],{})
        self.assertTrue(env['equal']);self.assertEqual(env['text'],'{}')

    def test_io_bookkeeping_is_not_exported_after_later_calls(self):
        self.module('io.v','__input="hello"; line=input(); function talk(){print("hi");return __output}')
        out=io.StringIO()
        with redirect_stdout(out):
            env=self.run_source('m=import("io.v"); answer=m.talk(); text=string(m)')
        self.assertEqual(env['answer'],'hi')
        self.assertEqual(env['m']['line'],'hello')
        self.assertNotIn('__input',env['m']);self.assertNotIn('__output',env['m'])
        self.assertNotIn('__output',env['text'])

    def test_parent_field_does_not_turn_module_data_into_scope_chain(self):
        self.module('m.v','function read(){return secret}; function update(){set secret=5}')
        env=self.run_source('m=import("m.v"); m["$PARENT"]={"secret":42}')
        for source in ('m.read()','m.update()'):
            with self.subTest(source=source),self.assertRaises((ValueError,NameError)):
                evaluate_source(source,env)

    def test_circular_import_uses_resolved_paths_and_recovers(self):
        self.module('a.v','b=import("sub/../a.v")')
        (self.root/'sub').mkdir()
        with self.assertRaisesRegex(ImportError,'Circular import'):
            self.run_source('m=import("a.v")')
        self.module('a.v','answer=42')
        self.assertEqual(self.run_source('m=import("a.v")')['m']['answer'],42)

    def test_indirect_cycle(self):
        self.module('a.v','b=import("b.v")')
        self.module('b.v','a=import("a.v")')
        with self.assertRaisesRegex(ImportError,'Circular import'):
            self.run_source('import("a.v")')

    def test_missing_invalid_paths_and_arity(self):
        for text,error in [('import("missing.v")',FileNotFoundError),('import(1)',TypeError),
                           ('import("")',ValueError),('import()',TypeError),('import("x","y")',TypeError)]:
            with self.subTest(text=text),self.assertRaises(error):self.run_source(text)

    def test_syntax_and_top_level_return_are_program_errors(self):
        for source,error in [('x=',SyntaxError),('return 42',ValueError),('break',ValueError)]:
            self.module('bad.v',source)
            with self.subTest(source=source),self.assertRaises(error):self.run_source('import("bad.v")')

    def test_exit_propagates_without_publishing_partial_module(self):
        self.module('stop.v','x=1; exit(7); x=2')
        result,env=evaluate_source('m=import("stop.v"); after=1',source_path=self.root/'main.v')
        self.assertEqual(result,(7,'exit'));self.assertNotIn('m',env);self.assertNotIn('after',env)

    def test_copy_is_a_record_copy_and_retains_function_identity(self):
        self.module('m.v','factor=2; function scale(x){return factor*x}')
        env=self.run_source('m=import("m.v"); c=copy(m); before=m==c; c.factor=9; answer=c.scale(5)')
        self.assertTrue(env['before']);self.assertEqual(env['answer'],10)
        self.assertEqual(env['m']['factor'],2)

    def test_native_calls_can_receive_and_return_module_objects(self):
        from unittest.mock import patch
        from native_functions import NATIVE_FUNCTIONS
        self.module('m.v','answer=42')
        with patch.dict(NATIVE_FUNCTIONS,{'identity':lambda m:m}):
            env=self.run_source('m=import("m.v"); f=native("identity",["m"]); alias=f(m); alias.answer=7')
        self.assertIs(env['m'],env['alias']);self.assertEqual(env['m']['answer'],7)

    def test_runner_resolves_main_file_from_another_directory(self):
        self.module('sub/value.v','answer=42')
        main=self.module('sub/main.v','m=import("value.v"); print(m.answer)')
        runner=Path(__file__).with_name('runner.py').resolve()
        result=subprocess.run([sys.executable,str(runner),str(main)],cwd=self.root,
                              capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,'42\n')


if __name__=='__main__':unittest.main()
