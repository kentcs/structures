// Creates or replaces json-io-output.json in the working directory.
io = import("modules/io.v");
record = {"name": "Ada", "scores": [10, 20, 30], "active": true};
io.writeJSON("json-io-output.json", record);
loaded = io.readJSON("json-io-output.json");
print(loaded.name);
print(loaded.scores[2]);
print(loaded == record);
