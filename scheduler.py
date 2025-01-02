import json
from pysat.pb import *
from pysat.formula import IDPool, WCNF
from pysat.examples.rc2 import RC2
from pysat.card import CardEnc
from pysat.solvers import Solver
import random








class CourseScheduler:
    def __init__(self, core_courses_file, methods_elective_files, systems_elective_files, cs_electives_file, sciences_electives_file, social_electives_file, user_input_file):
        with open(user_input_file, 'r') as file:
            user_input = json.load(file)
        self.current_semester = user_input['current_semester']
        self.taken_courses = user_input['courses_taken']
        self.preferred_courses_weights = user_input.get('preferred_courses', {})
        self.total_semesters = 8
        self.num_semesters = self.total_semesters - self.current_semester
        self.max_schedule_count = user_input['max_schedule_count']
        # print(self.max_schedule_count)
      
        self.courses = {}
        self.load_courses(core_courses_file, course_type='core')
        self.load_courses(cs_electives_file, course_type='cs_elective')
        self.load_courses(sciences_electives_file, course_type='science_elective')
        self.load_courses(social_electives_file, course_type='social_elective')
        self.load_courses(methods_elective_files, course_type='methods_elective')
        self.load_courses(systems_elective_files, course_type='systems_elective')

        self.total_credits = 120
        self.methods_electives_credits = 3
        self.systems_electives_credits = 3
        self.cs_electives_credits = 45
        self.sciences_electives_credits = 9
        self.social_electives_credits = 18

        self.courses_taken = []
        for courses in self.taken_courses.values():
            self.courses_taken.extend(courses)
        
        for course_code in self.courses_taken:
            if course_code in self.courses:
                self.total_credits -= self.courses[course_code]["credit_units"]
                if self.courses[course_code]["type"] == "cs_elective":
                    self.cs_electives_credits -= self.courses[course_code]["credit_units"]
                elif self.courses[course_code]["type"] == "science_elective":
                    self.sciences_electives_credits -= self.courses[course_code]["credit_units"]
                elif self.courses[course_code]["type"] == "social_elective":
                    self.social_electives_credits -= self.courses[course_code]["credit_units"]
                

    

        self.num_courses = len(self.courses)
        self.prerequisites = self.extract_prerequisites()
        self.course_codes = list(self.courses.keys())

        self.vpool = IDPool()
        self.cnf = WCNF()

    def load_courses(self, file_path, course_type=None):
        with open(file_path, 'r') as file:
            courses = json.load(file)
        for course in courses:
            course['type'] = course_type
            self.courses[course['code']] = course

    def extract_prerequisites(self):
        prerequisites = {}
        for course_code, course in self.courses.items():
            prereqs = course['prerequisites']
            prerequisites[course_code] = prereqs
        return prerequisites

    def var(self, c, s=None):
        if s is None:
            return self.vpool.id(f'c{c}')
        else:
            return self.vpool.id(f'c{c}_s{s}')


    def generate_constraints(self):


        

        # Create a dictionary to map clauses to their names
        self.templates = {}


        # Create a dictionary to map each course to its variable and semester variables
        self.course_vars = {}
        self.var_to_course = {}  # Reverse mapping dictionary
        for c, course_code in enumerate(self.courses):
            if course_code not in self.courses_taken:
                self.course_vars[course_code] = {
                    'var': self.var(c),
                    'semester_vars': [self.var(c, s) for s in range(self.num_semesters)]
                }
                self.var_to_course[self.var(c)] = course_code  # Map variable to course code
                for s in range(self.num_semesters):
                    self.var_to_course[self.var(c, s)] = (course_code, s)  # Map variable to course code and semester

        # All required core courses must be scheduled
        for course_code, course in self.courses.items():
            if course['type'] == 'core' and course_code not in self.courses_taken:
                clause = [self.var(self.course_codes.index(course_code))]
                self.cnf.append(clause)
                self.templates[f"Course {course_code} is a core requirement for CS."] = [clause]


        # Preferred courses
        for course_code, weight in self.preferred_courses_weights.items():
            if course_code in self.courses and course_code not in self.courses_taken:
                course_index = self.course_codes.index(course_code)
                clauses = []
                for s in range(self.num_semesters):
                    clause = [self.var(course_index, s)]
                    self.cnf.append(clause, weight=weight)
                    clauses.append(clause)
                self.templates[f"Course {course_code} is a course preferred by you."] = clauses
            else:
                print(f"Warning: Preferred course {course_code} not found in the course list.")

        # Total credits constraint
        all_courses = [self.var(self.course_codes.index(course_code)) for course_code in self.courses if course_code not in self.courses_taken]
        all_courses_total_credits = [course['credit_units'] for course in self.courses.values() if course['code'] not in self.courses_taken]
        clause = PBEnc.leq(lits=all_courses, weights=all_courses_total_credits, bound=self.total_credits, encoding=EncType.best, vpool=self.vpool).clauses
        # print(len(clause))
        self.cnf.extend(clause)
        self.templates[f"The total credits for all scheduled courses must sum up to {self.total_credits}."] = clause
       

        # Total credits constraint for CS electives
        if self.cs_electives_credits > 0:
            cs_electives = [self.var(self.course_codes.index(course_code)) for course_code, course in self.courses.items() if course["type"] == "cs_elective" and course_code not in self.courses_taken]
            cs_electives_total_credits = [course['credit_units'] for course in self.courses.values() if course['type'] == "cs_elective" and course['code'] not in self.courses_taken]
            clause = PBEnc.geq(lits=cs_electives, weights=cs_electives_total_credits, bound=15, encoding=EncType.best, vpool=self.vpool).clauses
            self.cnf.extend(clause)
            self.templates[f"The total credits for CS elective courses must sup to {self.cs_electives_credits}."] = clause

        # Total credits constraint for science courses
        if self.sciences_electives_credits > 0:
            science_electives = [self.var(self.course_codes.index(course_code)) for course_code, course in self.courses.items() if course["type"] == "science_elective" and course_code not in self.courses_taken]
            science_electives_total_credits = [course['credit_units'] for course in self.courses.values() if course['type'] == "science_elective" and course['code'] not in self.courses_taken]
            clause = PBEnc.equals(lits=science_electives, weights=science_electives_total_credits, bound=self.sciences_electives_credits, encoding=EncType.best, vpool=self.vpool).clauses
            self.cnf.extend(clause)
            self.templates[f"The total credits for science elective courses must sup up to {self.sciences_electives_credits}."] = clause
        else:
            clause = [[-self.var(self.course_codes.index(course_code))] for course_code, course in self.courses.items() if course["type"] == "science_elective"]
            # print(clause)
            self.cnf.extend(clause)
            self.templates["You cannot take any more science elective courses."] = clause
        

        # Total credits constraint for social courses
        if self.social_electives_credits > 0:
            social_electives = [self.var(self.course_codes.index(course_code)) for course_code, course in self.courses.items() if course["type"] == "social_elective" and course_code not in self.courses_taken]
            social_electives_total_credits = [course['credit_units'] for course in self.courses.values() if course['type'] == "social_elective" and course['code'] not in self.courses_taken]
            clause = PBEnc.equals(lits=social_electives, weights=social_electives_total_credits, bound=self.social_electives_credits, encoding=EncType.best, vpool=self.vpool).clauses
            self.cnf.extend(clause)

            self.templates[f"The total credits for social elective courses must sup to {self.social_electives_credits}."] = clause
        else:
            clause = [[-self.var(self.course_codes.index(course_code))] for course_code, course in self.courses.items() if course["type"] == "social_elective"]
            self.cnf.extend(clause)
            self.templates["You cannot take any more social/humanitites elective courses."] = clause


        # One methods elective must be scheduled
        if self.methods_electives_credits > 0:
            clause = [self.var(self.course_codes.index(course_code)) for course_code, course in self.courses.items() if course["type"] == "methods_elective" and course_code not in self.courses_taken]
            self.cnf.append(clause)
            self.templates["At least one methods elective must be scheduled."] = [clause]

        # One systems elective must be scheduled
        if self.systems_electives_credits > 0:
            clause = [self.var(self.course_codes.index(course_code)) for course_code, course in self.courses.items() if course["type"] == "systems_elective" and course_code not in self.courses_taken]
            self.cnf.append(clause)
            self.templates["At least one systems elective must be scheduled."] = [clause]


        # Minimum and maximum credit units per semester
        min_credits = 9
        max_credits = 15
        for s in range(self.num_semesters):
            semester_courses = [self.var(self.course_codes.index(course_code), s) for course_code in self.courses if course_code not in self.courses_taken]
            course_credits = [self.courses[course_code]['credit_units'] for course_code in self.courses if course_code not in self.courses_taken]
            clause = PBEnc.equals(lits=semester_courses, weights=course_credits, bound=max_credits, encoding=EncType.seqcounter, vpool=self.vpool).clauses
            self.cnf.extend(clause)
            self.templates[f"The total credits for semester {s + self.current_semester + 1} should not exceed {max_credits} credits."] = clause


        # If a course is scheduled, at least one of its corresponding variables for each semester must be true
        for course_code in self.courses:
            if course_code not in self.courses_taken:
                course_index = self.course_codes.index(course_code)
                # clause = [-self.var(course_index)] + [self.var(course_index, s) for s in range(self.num_semesters)]
                # self.cnf.append(clause)
                # self.templates[f"Course {course_code} should be scheduled in at least one semester."] = [clause]
                clauses = []
                course_semester_vars = CardEnc.equals(lits=[self.var(course_index, s) for s in range(self.num_semesters)], bound=1, vpool=self.vpool).clauses
                for c in course_semester_vars:
                    clauses.append([-self.var(course_index)] + c)
                self.cnf.extend(clauses)
                self.templates[f"Course {course_code} should be scheduled in a semester."] = clauses

        # If a course is not scheduled, none of its corresponding variables for each semester can be true
        for course_code in self.courses:
            if course_code not in self.courses_taken:
                course_index = self.course_codes.index(course_code)
                clauses = []
                for s in range(self.num_semesters):
                    clause = [self.var(course_index), -self.var(course_index, s)]
                    # print(clause)
                    self.cnf.append(clause)
                    clauses.append(clause)
                self.templates[f"Course {course_code} is not scheduled in any semester."] = clauses


        # Each course is assigned to at most one semester
        for course_code in self.courses:
            if course_code not in self.courses_taken:
                course_index = self.course_codes.index(course_code)
                clauses = PBEnc.atmost(lits=[self.var(course_index, s) for s in range(self.num_semesters)], bound=1, encoding=EncType.best, vpool=self.vpool).clauses
                # clause = CardEnc.atmost(lits=[self.var(course_index, s) for s in range(self.num_semesters)], bound=1, vpool=self.vpool)
                self.cnf.extend(clauses)
                self.templates[f"Course {course_code} can only be scheduled once."] = clauses


        # Prerequisites must be taken before the courses that require them
        for course_code, prereqs in self.prerequisites.items():
            if course_code not in self.courses_taken:
                course_index = self.course_codes.index(course_code)
                prereq_indices = [self.course_codes.index(prereq) for prereq in prereqs if prereq not in self.courses_taken]

                # Check if prerequisites are already satisfied by the courses taken
                if all(prereq in self.courses_taken for prereq in prereqs):
                    continue

                # If a course is scheduled in a specific semester, all of its (unsatisfied) prerequisites must be scheduled in previous semesters
                clauses = []
                for s in range(self.num_semesters ):

                    for prereq_index in prereq_indices:
                        clause = [-self.var(course_index, s)] + [self.var(prereq_index, t) for t in range(s)]
                        self.cnf.append(clause)
                        clauses.append(clause)
                        self.templates[f"Course {self.course_codes[prereq_index]} must be taken before semester {s + self.current_semester + 1} because it is a prerequisite for {course_code}."] = [clause]


        # A course and its unsatisfied prerequisite cannot be taken in the same semester
        for course_code, prereqs in self.prerequisites.items():
            if course_code not in self.courses_taken:
                course_index = self.course_codes.index(course_code)
                for prereq in prereqs:
                    if prereq not in self.courses_taken:
                        prereq_index = self.course_codes.index(prereq)
                        clauses = []
                        for s in range(self.num_semesters):
                            clause = [-self.var(course_index, s), -self.var(prereq_index, s)]
                    
                            self.cnf.append(clause)
                            clauses.append(clause)
                            self.templates[f"Course {course_code} and its prerequisite {prereq} cannot be taken in the same semester {s + self.current_semester + 1}."] = [clause]
                        

    def solve(self):
        self.generate_constraints()
        # print(len(self.cnf.hard+ self.cnf.soft))
        # print(self.var_to_course[2])
        # exit()
        # print(self.var_to_course[442])
        # print(self.var_to_course[440])

        # print(self.var_to_course)


        solver = Solver("g4")
        solver.append_formula(self.cnf.hard + self.cnf.soft)
        models = []
        count = 0
        while True:
            solver.solve()
            m = solver.get_model()
            if not m:
                break       
            models.append(m)
            # Block randomly a quarter of the courses in previous model
            to_block = []
            for c, course_code in enumerate(self.courses):
                for s in range(self.num_semesters):
                    if self.var(c, s) in m:
                        to_block.append([-self.var(c, s)])
            quarter_to_block = random.choices(to_block, k=len(to_block)//4)
            for clause in quarter_to_block:
                solver.add_clause(clause)
            
            count += 1
            if count == self.max_schedule_count:
                break
    
        schedules = []
        true_courses_lits = []
        for model in models:
            schedule = [[] for _ in range(self.total_semesters)]
            
            # Add previously taken courses to the schedule
            for semester, courses in self.taken_courses.items():
                semester_index = int(semester) - 1
                schedule[semester_index].extend(courses)
            true_lits = []
            for c, course_code in enumerate(self.courses):
                clauses = []
                for s in range(self.num_semesters):
                    if self.var(c, s) in model:
                        schedule[s + self.current_semester ].append(course_code)
                        clauses.append([self.var(c, s)])
                        # self.templates[f"Course {course_code} is scheduled in semester {s + self.current_semester + 1}."] = clauses
                        true_lits.append([self.var(c, s)])
            true_courses_lits.append(true_lits)      
            schedules.append(schedule)
   
        return schedules, models, true_courses_lits



    