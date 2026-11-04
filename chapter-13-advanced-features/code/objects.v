student = {"name": "Ada", "score": 87};
student.score = 90;
student.passed = true;
print(student);

// Records and lists combine through the existing suffix syntax.
classroom = [student, {"name": "Lee", "score": 85}];
classroom[1].score = 88;
print(classroom[1]["score"]);

// Assignment shares an object. Deep copying makes an independent record.
alias = student;
alias.score = 95;
mycopy = copy(student);
mycopy.score = 100;
print(student.score);
print(mycopy.score);

// A field named $PARENT is ordinary data, with no implicit lookup chain.
family = {"$PARENT": {"name": "Mae"}, "name": "Lee"};
print(family["$PARENT"].name);

// Cycles can be printed, compared, and copied.
cycle = {};
cycle.self = cycle;
print(cycle);
print(cycle == copy(cycle));
