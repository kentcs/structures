// Creates or replaces file-io-output.txt in the current working directory.
io = import("modules/io.v");
io.write("file-io-output.txt", "Hello from file I/O!\n");
print(io.read("file-io-output.txt"));
