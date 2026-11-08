import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import evaluator
from evaluator import evaluate_source
from native_functions import NATIVE_FUNCTIONS, register_native


class NativeTests(unittest.TestCase):
    def run_source(self, source):
        result, env = evaluate_source(source)
        self.assertEqual(result, (None, None))
        return env

    def test_constructor_connects_without_calling(self):
        host = Mock(return_value=7)
        with patch.dict(NATIVE_FUNCTIONS, {"sample": host}):
            env = self.run_source('f=native("sample",["a","b"])')
            host.assert_not_called()
            self.assertTrue(evaluator.is_function(env['f']))
            result, env = evaluate_source('answer=f(2,5)', env)
            self.assertEqual(result, (None, None))
            self.assertEqual(env['answer'], 7)
            host.assert_called_once_with(2, 5)

    def test_math_examples_and_immediate_call(self):
        env = self.run_source('sqrt=native("math.sqrt",["x"]); x=sqrt(9); y=native("math.hypot",["a","b"])(3,4)')
        self.assertEqual((env['x'], env['y']), (3, 5))

    def test_pass_store_return_and_capture(self):
        env = self.run_source('''
            function apply(f,x) { return f(x) };
            function factory() {
                f=native("math.sqrt",["x"]);
                return function(x) { return f(x) }
            };
            methods={"sqrt":native("math.sqrt",["x"])};
            funcs=[methods.sqrt]; reader=factory();
            a=apply(funcs[0],16); b=reader(25); c=methods.sqrt(36)
        ''')
        self.assertEqual((env['a'],env['b'],env['c']), (4,5,6))

    def test_identity_type_display_and_copy(self):
        env = self.run_source('''
            f=native("math.sqrt",["x"]); g=native("math.sqrt",["x"]);
            alias=f; same=alias==f; different=f!=g;
            copied=copy(f); kind=type(f); text=string(f);
            constructorSame=native==native;
            constructorAlias=native; h=constructorAlias("math.sqrt",["x"]);
            answer=h(49)
        ''')
        self.assertTrue(env['same']); self.assertTrue(env['different'])
        self.assertTrue(env['constructorSame'])
        self.assertIs(env['copied'],env['f'])
        self.assertEqual((env['kind'],env['text'],env['answer']),('function','<function>',7))

    def test_parameter_list_is_copied(self):
        env=self.run_source('names=["x"]; f=native("math.sqrt",names); names[0]="other"; answer=f(4)')
        self.assertEqual(env['f']['parameters'],['x'])
        self.assertEqual(env['answer'],2)

    def test_native_can_be_shadowed(self):
        env=self.run_source('native=function(x) {return x+1}; answer=native(2)')
        self.assertEqual(env['answer'],3)

    def test_invalid_constructor_arguments(self):
        for source, error in [
            ('native(1,[])',TypeError),
            ('native("math.sqrt","x")',TypeError),
            ('native("math.sqrt",[1])',ValueError),
            ('native("math.sqrt",["bad-name"])',ValueError),
            ('native("math.sqrt",["function"])',ValueError),
            ('native("math.sqrt",["x","x"])',ValueError),
            ('native("missing",[])',ValueError),
            ('native("math.sqrt")',TypeError),
        ]:
            with self.subTest(source=source),self.assertRaises(error):
                self.run_source(source)

    def test_arity_checked_before_host_invocation(self):
        host=Mock(return_value=1)
        with patch.dict(NATIVE_FUNCTIONS,{"sample":host}):
            for args in ('','1,2'):
                with self.subTest(args=args),self.assertRaises(TypeError):
                    self.run_source('f=native("sample",["x"]); f('+args+')')
            host.assert_not_called()

    def test_argument_order_even_when_arity_is_wrong(self):
        host=Mock(return_value=None)
        with patch.dict(NATIVE_FUNCTIONS,{"sample":host}),patch('builtins.input',side_effect=['first','second']) as read:
            with self.assertRaises(TypeError):
                self.run_source('f=native("sample",["x"]); f(input(),input())')
            self.assertEqual(read.call_count,2)
            host.assert_not_called()

    def test_argument_values_evaluate_left_to_right(self):
        host=Mock(return_value=1)
        with patch.dict(NATIVE_FUNCTIONS,{"sample":host}),patch('builtins.input',side_effect=['first','second']):
            self.run_source('f=native("sample",["a","b"]); f(input(),input())')
            host.assert_called_once_with('first','second')

    def test_argument_status_skips_host(self):
        host=Mock(return_value=None)
        with patch.dict(NATIVE_FUNCTIONS,{"sample":host}):
            result,_=evaluate_source('f=native("sample",["x"]); function stop(){exit(7)}; f(stop())')
            self.assertEqual(result,(7,'exit'));host.assert_not_called()

    def test_host_results_and_mutable_argument_aliases(self):
        def change(items):
            items[0]=42
            return {'items':items,'empty':None,'ok':True}
        with patch.dict(NATIVE_FUNCTIONS,{"sample":change}):
            env=self.run_source('a=[1]; f=native("sample",["items"]); result=f(a)')
            self.assertIs(env['a'],env['result']['items'])
            self.assertEqual(env['a'],[42])
            self.assertIsNone(env['result']['empty'])

    def test_cycles_are_valid_results(self):
        value=[]; value.append(value)
        with patch.dict(NATIVE_FUNCTIONS,{"cycle":lambda:value}):
            env=self.run_source('f=native("cycle",[]); result=f()')
            self.assertIs(env['result'][0],env['result'])

    def test_python_only_results_are_rejected(self):
        for value in ((1,2),object(),{1:'bad'},[object()]):
            with self.subTest(value=type(value)),patch.dict(NATIVE_FUNCTIONS,{"bad":lambda:value}):
                with self.assertRaises(TypeError):self.run_source('f=native("bad",[]); f()')

    def test_host_exceptions_propagate(self):
        with self.assertRaises(ValueError):
            self.run_source('f=native("math.sqrt",["x"]); f(-1)')
        with self.assertRaises(TypeError):
            self.run_source('f=native("math.sqrt",["x"]); f(true)')

    def test_internals_remain_inaccessible(self):
        for suffix in ('.native','.parameters','["name"]'):
            with self.subTest(suffix=suffix),self.assertRaises(TypeError):
                self.run_source('f=native("math.sqrt",["x"]); f'+suffix)

    def test_host_registration_and_zero_arguments(self):
        with patch.dict(NATIVE_FUNCTIONS):
            register_native('answer',lambda:42)
            env=self.run_source('f=native("answer",[]); answer=f()')
            self.assertEqual(env['answer'],42)
        for name,implementation in [('',lambda:1),('x',1)]:
            with self.assertRaises(TypeError):register_native(name,implementation)

    def test_example_file(self):
        from pathlib import Path
        out=io.StringIO()
        with redirect_stdout(out):
            self.run_source(Path(__file__).with_name('native.v').read_text())
        self.assertEqual(out.getvalue(),'3.0\n5.0\n7.0\nfunction\ntrue\n')


if __name__=='__main__':unittest.main()
