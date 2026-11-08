// File I/O library. Import this module and choose any namespace name.
read = native("io.read", ["path"]);
write = native("io.write", ["path", "text"]);
readJSON = native("io.readJSON", ["path"]);
writeJSON = native("io.writeJSON", ["path", "value"]);
