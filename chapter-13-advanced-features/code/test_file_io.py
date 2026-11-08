import json
import math
from pathlib import Path
import tempfile
import unittest

from evaluator import evaluate_source
import file_io


class FileIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "data.txt"
        self.path = json.dumps(str(self.target))

    def run_source(self, source):
        source = 'io=import("modules/io.v");' + source
        result, env = evaluate_source(source, source_path=Path(__file__).with_name("main.v"))
        self.assertEqual(result, (None, None))
        return env

    def test_text_round_trip_empty_and_truncate(self):
        for text in ("café ☕\nsecond line\n", "x", ""):
            env = self.run_source(f'written=io.write({self.path},{json.dumps(text,ensure_ascii=False)});text=io.read({self.path})')
            self.assertIsNone(env['written'])
            self.assertEqual(env['text'], text)
            self.assertEqual(self.target.read_text(), text)

    def test_json_nested_round_trip(self):
        env = self.run_source(f'''data={{"name":"café ☕","count":3,"price":2.5,"ok":true,
            "missing":null,"items":[1,"two",false,{{"nested":[]}}]}};
            written=io.writeJSON({self.path},data);loaded=io.readJSON({self.path});
            same=loaded==data;loaded.count=4;original=data.count''')
        self.assertIsNone(env['written'])
        self.assertTrue(env['same'])
        self.assertEqual(env['original'], 3)
        self.assertEqual(json.loads(self.target.read_text())['name'], 'café ☕')

    def test_json_value_kinds(self):
        for expression in ('{}','[]','null','true','false','12','-2.5','"hello"','[{},[],null]'):
            with self.subTest(expression=expression):
                env=self.run_source(f'before={expression};io.writeJSON({self.path},before);after=io.readJSON({self.path});same=before==after')
                self.assertTrue(env['same'])

    def test_shared_data_and_function_values(self):
        env=self.run_source(f'a=[1,2];io.writeJSON({self.path},[a,a]);loaded=io.readJSON({self.path});readAlias=io.read;kind=type(io.readJSON)')
        self.assertEqual(env['loaded'], [[1,2],[1,2]])
        self.assertEqual(env['kind'], 'function')
        self.assertIs(env['readAlias'],env['io']['read'])

    def test_bad_json_writes_preserve_existing_file(self):
        for source in (
            f'io.writeJSON({self.path},function(){{}})',
            f'a=[0];a[0]=a;io.writeJSON({self.path},a)',
            f'a={{}};a.self=a;io.writeJSON({self.path},a)',
            f'io.writeJSON({self.path},{{"nested":[function(){{}}]}})',
            f'io.writeJSON({self.path})',
        ):
            self.target.write_text('keep')
            with self.subTest(source=source), self.assertRaises((TypeError,ValueError)):
                self.run_source(source)
            self.assertEqual(self.target.read_text(),'keep')
        for number in (math.nan, math.inf, -math.inf):
            self.target.write_text('keep')
            with self.assertRaises(ValueError):
                file_io.write_json(str(self.target),number)
            self.assertEqual(self.target.read_text(),'keep')

    def test_invalid_json_and_io_errors(self):
        for text in ('','{oops}','{} {}','{"number":NaN}','[1,]'):
            self.target.write_text(text)
            with self.subTest(text=text),self.assertRaises(ValueError):
                self.run_source(f'io.readJSON({self.path})')
        for source in ('io.read(1)','io.write(1,"text")','io.readJSON(1)',
                       'io.writeJSON(1,{})','io.readJSON()',
                       f'io.write({self.path},1)',
                       f'io.read({json.dumps(str(self.root/"missing"))})',
                       f'io.writeJSON({json.dumps(str(self.root))},{{}})'):
            with self.subTest(source=source),self.assertRaises((TypeError,OSError)):
                self.run_source(source)

    def test_argument_exit_prevents_write(self):
        result,env=evaluate_source(f'io=import("modules/io.v");function stop(){{exit(7)}};io.writeJSON({self.path},stop())',source_path=Path(__file__).with_name('main.v'))
        self.assertEqual(result,(7,'exit'))
        self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
