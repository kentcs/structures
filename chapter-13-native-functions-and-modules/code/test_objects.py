import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import evaluator
import parser
import tokenizer


def exit_node(value=7):
    return {"tag": "exit", "expression": {"tag": "number", "value": value}}


class ObjectParsingTests(unittest.TestCase):
    def parse(self, source):
        return parser.parse(tokenizer.tokenize(source))

    def test_empty_literal(self):
        node,rest=parser.parse_expression(tokenizer.tokenize('{}'))
        self.assertEqual(node,{'tag':'object','fields':[]})
        self.assertEqual([token['tag'] for token in rest],[None])

    def test_computed_keys_and_nested_values(self):
        node,rest=parser.parse_expression(tokenizer.tokenize('{key+"x":[{}],"other":{"n":1}}'))
        self.assertEqual(node['tag'],'object')
        self.assertEqual(len(node['fields']),2)
        self.assertEqual(node['fields'][0][0]['tag'],'+')
        self.assertEqual(node['fields'][1][1]['tag'],'object')
        self.assertEqual([token['tag'] for token in rest],[None])

    def test_literal_inside_statement_blocks(self):
        self.parse('if(true){a={"x":1};}; while(false){a={};}')

    def test_bad_literals_and_object_as_block(self):
        for source in ('x={"a":1,}','x={"a" 1}','x={"a":}','x={,}','x={"a":1','if(true){"a":1}'):
            with self.subTest(source=source),self.assertRaises(SyntaxError):
                self.parse(source)


class ObjectConstructionTests(unittest.TestCase):
    def run_source(self, source, env=None):
        env = {} if env is None else env
        result, env = evaluator.evaluate_source(source, env)
        return result, env

    def test_empty_computed_and_nested_literals(self):
        _, env = self.run_source('key="score"; empty={}; student={"name":"Ada",key:87,"data":[{"ok":true}]}')
        self.assertEqual(env['empty'], {})
        self.assertEqual(env['student'], {'name':'Ada','score':87,'data':[{'ok':True}]})

    def test_duplicate_evaluated_keys_rejected(self):
        with self.assertRaises(ValueError):
            self.run_source('k="a"; x={"a":1,k:2}')

    def test_key_before_value_and_fields_left_to_right(self):
        with patch('builtins.input',side_effect=['first','1','second','2']) as read:
            _, env = self.run_source('a={input():input(),input():input()}')
        self.assertEqual(list(env['a'].items()),[('first','1'),('second','2')])
        self.assertEqual(read.call_count,4)

    def test_duplicate_or_invalid_key_does_not_evaluate_value(self):
        for source,error in (('a={1:input()}',TypeError),('a={"x":1,"x":input()}',ValueError)):
            with self.subTest(source=source), patch('builtins.input') as read:
                with self.assertRaises(error): self.run_source(source)
                read.assert_not_called()

    def test_exit_from_literal_key_or_value_stops_construction(self):
        # exit can no longer sit inside an object literal in real source,
        # since it cannot nest inside any expression; each node below is
        # built directly to check the evaluator's own propagation.
        input_node = {"tag": "input", "prompt": None}
        cases = [
            {"tag": "object", "fields": [(exit_node(7), input_node)]},
            {"tag": "object", "fields": [
                ({"tag": "string", "value": "x"}, exit_node(7)),
                (input_node, input_node)]},
        ]
        for node in cases:
            with self.subTest(fields=len(node["fields"])):
                env = {'a': 'original'}
                target = {"tag": "assign", "target": {"tag": "identifier", "value": "a"},
                         "expression": node}
                with patch('builtins.input') as read:
                    result = evaluator.evaluate(target, env)
                self.assertEqual(result,(7,'exit'))
                self.assertEqual(env['a'],'original')
                read.assert_not_called()



class ObjectFieldTests(unittest.TestCase):
    def run_source(self, source, env=None):
        env = {} if env is None else env
        result, env = evaluator.evaluate_source(source, env)
        return result, env

    def test_reads_updates_new_fields_and_mixed_chains(self):
        _, env = self.run_source('students=[{"scores":[80,90]}]; students[0].scores[1]=95; students[0].passed=true; x=students[0]["scores"][1]')
        self.assertEqual(env['x'],95)
        self.assertTrue(env['students'][0]['passed'])

    def test_dot_and_bracket_ast_are_identical(self):
        self.assertEqual(parser.parse(tokenizer.tokenize('x=obj.field')),parser.parse(tokenizer.tokenize('x=obj["field"]')))

    def test_alias_mutates_but_rebinding_does_not(self):
        _, env = self.run_source('a={"x":1}; b=a; b.x=2; b={"x":3}')
        self.assertEqual(env['a'],{'x':2})
        self.assertEqual(env['b'],{'x':3})

    def test_missing_field_raises(self):
        with self.assertRaises(KeyError):
            self.run_source('a={}; x=a.missing')

    def test_parent_field_is_only_data(self):
        _, env = self.run_source('a={"$PARENT":{"birthplace":"Kent"}}; x=a["$PARENT"].birthplace')
        self.assertEqual(env['x'],'Kent')
        with self.assertRaises(KeyError):
            self.run_source('a={"$PARENT":{"birthplace":"Kent"}}; x=a.birthplace')

    def test_invalid_keys_for_literal_read_and_write(self):
        for key in ('1','true','[]','{}'):
            for source in (f'a={{{key}:1}}',f'a={{}}; x=a[{key}]',f'a={{}}; a[{key}]=1'):
                with self.subTest(source=source), self.assertRaises(TypeError):
                    self.run_source(source)

    def test_blocks_and_literals_remain_distinct(self):
        _, env = self.run_source('a={}; if(true){a.x={};}; while(false){};')
        self.assertEqual(env['a'],{'x':{}})
        with self.assertRaises(SyntaxError):
            self.run_source('if(true){"x":1}')

    def test_exit_from_read_or_write_preserves_state(self):
        # exit can no longer sit inside field access or assignment in real
        # source, since it cannot nest inside any expression; each node
        # below is built directly to check the evaluator's own propagation.
        a_id = {"tag": "identifier", "value": "a"}
        x_key = {"tag": "string", "value": "x"}
        field_key = {"tag": "string", "value": "field"}
        input_node = {"tag": "input", "prompt": None}
        x_target = {"tag": "identifier", "value": "x"}
        cases = [
            {"tag": "assign", "target": x_target,
             "expression": {"tag": "complex", "base": a_id, "index": exit_node(7)}},
            {"tag": "assign",
             "target": {"tag": "complex", "base": a_id, "index": exit_node(7)},
             "expression": input_node},
            {"tag": "assign",
             "target": {"tag": "complex", "base": a_id, "index": x_key},
             "expression": exit_node(7)},
            {"tag": "assign", "target": x_target,
             "expression": {"tag": "complex", "base": exit_node(7), "index": field_key}},
            {"tag": "assign",
             "target": {"tag": "complex",
                        "base": {"tag": "complex", "base": a_id, "index": exit_node(7)},
                        "index": field_key},
             "expression": input_node},
        ]
        for index, node in enumerate(cases):
            with self.subTest(case=index):
                env={'a':{'x':1}}
                with patch('builtins.input') as read:
                    result = evaluator.evaluate(node, env)
                self.assertEqual(result,(7,'exit'))
                self.assertEqual(env['a'],{'x':1})
                read.assert_not_called()

    def test_assignment_checks_key_before_right_hand_value(self):
        with patch('builtins.input') as read:
            with self.assertRaises(TypeError): self.run_source('a={}; a[1]=input()')
            read.assert_not_called()



class ObjectEqualityTests(unittest.TestCase):
    def run_source(self, source, env=None):
        env = {} if env is None else env
        result, env = evaluator.evaluate_source(source, env)
        return result, env

    def test_equality_ignores_order_and_distinguishes_boolean(self):
        _, env=self.run_source('a={"x":1,"y":[{"ok":true}]}; b={"y":[{"ok":true}],"x":1.0}; eq=a==b; neq=a!={"x":1,"y":[{"ok":1}]}; mixed=a==[]')
        self.assertTrue(env['eq']); self.assertTrue(env['neq']); self.assertFalse(env['mixed'])

    def test_cyclic_equality_detects_differences(self):
        _, env=self.run_source('a={}; a.self=a; b={}; b.self=b; same=a==b; b.extra=1; different=a!=b')
        self.assertTrue(env['same']); self.assertTrue(env['different'])



class ObjectDisplayTests(unittest.TestCase):
    def run_source(self, source, env=None):
        env = {} if env is None else env
        result, env = evaluator.evaluate_source(source, env)
        return result, env

    def test_cycles_and_shared_values_print_safely(self):
        _,env=self.run_source('a={}; items=[a]; a.items=items; text=string(a); shared={"x":1}; repeated=string([shared,shared])')
        self.assertEqual(env['text'],'{"items": [{...}]}')
        self.assertEqual(env['repeated'],'[{"x": 1}, {"x": 1}]')

    def test_print_and_string_preserve_insertion_order(self):
        out=io.StringIO()
        with redirect_stdout(out):
            _,env=self.run_source('a={"b":true,"a":["hi"]}; print(a); text=string(a)')
        self.assertEqual(out.getvalue(),'{"b": true, "a": ["hi"]}\n')
        self.assertEqual(env['text'],out.getvalue().strip())
        self.assertEqual(env['__output'],env['text'])


class ObjectCopyTests(unittest.TestCase):
    def run_source(self, source, env=None):
        env = {} if env is None else env
        result, env = evaluator.evaluate_source(source, env)
        return result, env

    def test_deep_copy_preserves_internal_aliases_and_mixed_cycles(self):
        _,env=self.run_source('child={"n":1}; a={"one":child,"two":child,"items":[]}; a.items=a.items+[a]; b=copy(a); equal=a==b; b.one.n=99')
        a,b=env['a'],env['b']
        self.assertTrue(env['equal']); self.assertIsNot(a,b)
        self.assertIs(b['one'],b['two']); self.assertIs(b['items'][0],b)
        self.assertIsNot(a['one'],b['one']); self.assertEqual(a['one']['n'],1)

    def test_copy_empty_object_and_self_cycle(self):
        _,env=self.run_source('a={}; a.self=a; b=copy(a); empty=copy({})')
        self.assertIsNot(env['a'],env['b'])
        self.assertIs(env['b']['self'],env['b'])
        self.assertEqual(env['empty'],{})

    def test_copy_of_list_containing_objects_is_independent(self):
        _,env=self.run_source('a=[{"n":1}]; b=copy(a); b[0].n=2')
        self.assertEqual(env['a'],[{'n':1}])
        self.assertEqual(env['b'],[{'n':2}])


class ObjectTypeTests(unittest.TestCase):
    def run_source(self, source, env=None):
        env = {} if env is None else env
        result, env = evaluator.evaluate_source(source, env)
        return result, env

    def test_objects_rejected_by_sequence_numeric_and_boolean_operations(self):
        for expr in ('number({})','boolean({})','length({})','head({})','tail({})','slice({},0,0)','{}+{}','{}<{}'):
            with self.subTest(expr=expr),self.assertRaises(TypeError): self.run_source('x='+expr)
    def test_object_type_and_exit_propagation(self):
        _,env=self.run_source('kind=type({})')
        self.assertEqual(env['kind'],'object')
        # exit can no longer sit inside these operations' argument in real
        # source, since it cannot nest inside any expression; each node is
        # built directly to check the evaluator's own propagation.
        tags = {'type': 'type_query', 'string': 'string_conversion', 'copy': 'copy',
               'number': 'number_conversion', 'boolean': 'boolean_conversion'}
        for operation, tag in tags.items():
            with self.subTest(operation=operation):
                node = {"tag": "assign", "target": {"tag": "identifier", "value": "x"},
                       "expression": {"tag": tag, "expression": exit_node(7)}}
                env = {}
                result = evaluator.evaluate(node, env)
                self.assertEqual(result,(7,'exit'))
                self.assertNotIn('x',env)


class ObjectExampleTests(unittest.TestCase):
    def test_runnable_objects_example(self):
        from pathlib import Path
        out=io.StringIO()
        with redirect_stdout(out):
            result,_=evaluator.evaluate_source(Path(__file__).with_name('objects.v').read_text())
        self.assertEqual(result,(None,None))
        self.assertEqual(out.getvalue(),'{"name": "Ada", "score": 90, "passed": true}\n88\n95\n100\nMae\n{"self": {...}}\ntrue\n')

    def test_field_operations_do_not_walk_environments(self):
        ast,_=parser.parse_expression(tokenizer.tokenize('a["$PARENT"].name'))
        assignment,_=parser.parse_statement(tokenizer.tokenize('a.score=90'))
        env={'a':{'$PARENT':{'name':'Mae'}}}
        with patch.object(evaluator,'global_environment',side_effect=AssertionError('environment traversal')):
            self.assertEqual(evaluator.evaluate(ast,env),('Mae',None))
            evaluator.evaluate(assignment,env)
        self.assertEqual(env['a']['score'],90)
