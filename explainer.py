from pysat.examples.optux import OptUx
from pysat.examples.lbx import LBX
from pysat.formula import IDPool, WCNF, CNF
from pysat.examples.rc2 import RC2
from pysat.solvers import Solver
import re
import copy
from sentence_transformers import SentenceTransformer, SimilarityFunction
from utils import explanation, SAT, repair, skeptical_entailment, getMCS, add_relevant_clauses
import openai


#########################################################################
''' OpenAI Key'''
openai.api_key=""
#########################################################################



def post_process_explanation(explanation, query, schedule, course_descriptions):
    # Get the scheduled course codes
    scheduled_course_codes = [course for semester in schedule for course in semester]
    
    # Filter the course descriptions to include only the scheduled courses
    scheduled_course_descriptions = {course: desc for course, desc in course_descriptions.items() if course in scheduled_course_codes}
    
    # Format the schedule and course descriptions
    schedule_str = "\n".join([f"Semester {i + 1}: {', '.join(courses)}" for i, courses in enumerate(schedule)])
    course_descriptions_str = "\n".join([f"{course}: {desc}" for course, desc in scheduled_course_descriptions.items()])
   
    prompt = f"""
You are an AI assistant helping a student understand their course schedule explanations. Given the schedule, relevant course descriptions, and an explanation for a constrastive query, your task is to format the explanation in a more understandable, concise, and coherent manner while providing additional information if necessary. Always contextualize the explanation with respect to the query. Do not change the meaning or content of the explanation. If the explantion is empty, provide a relevant response to the query.

Schedule:
{schedule_str}

Relevant Course Descriptions:
{course_descriptions_str}


Constrastive Query:
{query}
Explanation:
{explanation}
Post-processed explanation:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI assistant helping a student understand their course schedule explanations."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        n=1,
        stop=None,
        temperature=0.4,
    )
    post_processed_explanation = response.choices[0].message['content'].strip()
    return post_processed_explanation




def process_query(scheduler, schedule, query):

    # Format the schedule and course descriptions
    schedule_str = "\n".join([f"Semester {i + 1}: {', '.join(courses)}" for i, courses in enumerate(schedule)])
    # course_descriptions_str = "\n".join([f"{course}: {desc}" for course, desc in scheduled_course_descriptions.items()])
    

    # Format the course names
    course_info = "\n".join([f"{course}" for course, desc in scheduler.courses.items()])

    prompt = f"""
    You are an AI assistant helping to parse contrastive queries. You are given the schedule and available courses names, and your task is to extract from the query the course names, their corresponding semesters (if any), and whether each course is a positive (to be added) or negative (to be removed) condition. 

    If a course name is partially specified, find the best match in the course information. Otherwise, use the specified course name.
    If no semester is specified for a course, first try to extract the semester value from the context of the query or the courses in the schedule. For example, for query "why not course X instead of Y?", the semester value should that of Y, which should be in the schedule. Otherwise, use 'None' as the semester value.    
    
    Extract the course names, semesters, and conditions in the following format:
    Course Name 1, Semester, Condition (Positive/Negative)
    Course Name 2, Semester, Condition (Positive/Negative)
    ...

    Example 1:
    Courses:
    {course_info}
    
    Schedule:
    Semester 1: E81 CSE 131, E81 CSE 132, E81 CSE 240, L24 MATH 131, L24 MATH 132
    Semester 2: E81 CSE 361S, L24 MATH 233, E35 ESE 260, L41 BIOL 2960, L33 Psych 100B
    Semester 3: E81 CSE 237S, L59 Engr 310, CWP 100, L24 MATH 3200, L24 MATH 217
    
    Query: 
    Why CSE 237S in semester 3? 
    Extracted information: 
    E81 CSE 237S, Semester: 3, Condition: Negative

    Example 2:
    Courses:
    {course_info}
    
    Schedule:
    Semester 1: E81 CSE 131, E81 CSE 132, E81 CSE 240, L24 MATH 131, L24 MATH 132
    Semester 2: E81 CSE 361S, L24 MATH 233, E35 ESE 260, L41 BIOL 2960, L33 Psych 100B
    Semester 3: E81 CSE 237S, L59 Engr 310, CWP 100, L24 MATH 3200, L24 MATH 217
    
    Query: 
    Why not cse 500?
    Extracted information: 
    Course Name: E81 CSE 500, Semester: None, Condition: Positive
    
    Example 3:
    Courses:
    {course_info}
    
    Schedule:
    Semester 1: E81 CSE 131, E81 CSE 132, E81 CSE 240, L24 MATH 131, L24 MATH 132
    Semester 2: E81 CSE 361S, L24 MATH 233, E35 ESE 260, L41 BIOL 2960, L33 Psych 100B
    Semester 3: E81 CSE 237S, L59 Engr 310, CWP 100, L24 MATH 3200, L24 MATH 217
   
    Query:
    Why CWP 100 instead of cse 260M?
    Extracted information:
    Course Name: CWP 100, Semester: 3, Condition: Negative
    Course Name: E81 CSE 260M, Semester: 3, Condition: Positive

    Example 4:
    Courses:
    {course_info}
    
    Schedule:
    Semester 1: E81 CSE 131, E81 CSE 132, E81 CSE 240, L24 MATH 131, L24 MATH 132
    Semester 2: E81 CSE 361S, L24 MATH 233, E35 ESE 260, L41 BIOL 2960, L33 Psych 100B
    Semester 3: E81 CSE 237S, L59 Engr 310, CWP 100, L24 MATH 3200, L24 MATH 217
    
    Query:
    Why not cse 332s instead of ESE 260?
    Extracted information:
    Course Name: E81 CSE 332S, Semester: 2, Condition: Positive
    Course Name: E35 ESE 260, Semester: 2, Condition: Negative

    Example 5:
    Courses:
    {course_info}
    
    Schedule:
    Semester 1: E81 CSE 131, E81 CSE 132, E81 CSE 240, L24 MATH 131, L24 MATH 132
    Semester 2: E81 CSE 361S, L24 MATH 233, E35 ESE 260, L41 BIOL 2960, L33 Psych 100B
    Semester 3: E81 CSE 237S, L59 Engr 310, CWP 100, L24 MATH 3200, L24 MATH 217    

    Query:
    Why cse 240 in semester 1 and psych 100B in semester 2?
    Extracted information:
    Course Name: E81 CSE 240, Semester: 1, Condition: Negative
    Course Name: L33 Psych 100B, Semester: 2, Condition: Negative



    Courses:
    {course_info}

    Schedule:
    {schedule_str}

    Query: {query}

    Extracted information:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI assistant and your task is to extract information a user queries."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        n=1,
        stop=None,
        temperature=0.2,
    )

    extracted_info = response.choices[0].message['content'].strip().split('\n')

    return extracted_info

def post_process_query(scheduler, extracted_info):
    print(extracted_info)
    query_data = []
    for info in extracted_info:
        course_name, semester, condition = info.split(',')
        print(course_name)

        course_name = course_name.removeprefix("Course Name: ")
        print(course_name)
    
        semester = semester.strip(" Semester:")
        condition = condition.strip(" Condition:").lower()

        if course_name in scheduler.courses_taken:
            query_data.append((course_name, semester, f'{course_name} has already been taken in a past semester.', ''))

        elif course_name in scheduler.courses:
            if semester.lower() == 'none' or semester.lower() == 'non' or semester.lower() == '':
                if condition == 'positive':
                    # query_vars.append(scheduler.course_vars[course_name]['var'])
                    query_data.append((course_name, None, True, scheduler.course_vars[course_name]['var']))
                elif condition == 'negative':
                    # query_vars.append(-scheduler.course_vars[course_name]['var'])
                    query_data.append((course_name, None, False, scheduler.course_vars[course_name]['var']))
                    # print(query_data)
            else:
                if int(semester) > 8:
                    query_data.append((course_name, semester, f'There is no semester {int(semester)}. The maximum amount of semesters is 8.', ''))
                elif int(semester) <= scheduler.current_semester:
                    query_data.append((course_name, semester, f'Semester {int(semester)} has already passed.', ''))
                
                else:
                    semester_number = int(semester) - scheduler.current_semester - 1
                    if condition == 'positive':
                        # query_vars.append(scheduler.course_vars[course_name]['semester_vars'][semester_number])
                        # print(course_name, semester_number)
                        query_data.append((course_name, semester_number, True, scheduler.course_vars[course_name]['semester_vars'][semester_number]))
                    elif condition == 'negative':
                        # query_vars.append(-scheduler.course_vars[course_name]['semester_vars'][semester_number])
                        query_data.append((course_name, semester_number, False, scheduler.course_vars[course_name]['semester_vars'][semester_number]))

        else:
            query_data.append((course_name, semester, 'This course does not exist.', ''))

    return query_data





def contrastive_explanations(scheduler, schedules, current_schedule_index, true_lits, query_data):
    """ Contrastive Explanation Generation"""
    # Works well for one query now. 

    courses_in_query = [course[0] for course in query_data]
    scheduled_courses = [course for semester in schedules[current_schedule_index] for course in semester]
    updated_true_lits = copy.deepcopy(true_lits[current_schedule_index])

    Explanations = []
    pos_queries = CNF()
    neg_queries = CNF()
    all_pos_query_courses = []
    all_neg_query_courses = []

    
    # Construct the query clauses
    for query_course_code, semester_number, condition, query_var in query_data:
        # print(query_course_code, semester_number, condition, query_var)

        
        
        if condition == 'This course does not exist.':
            Explanations.append(f"{query_course_code} does not exist in the available course catalog.")
            return Explanations
        elif condition == f'Semester {semester_number} has already passed.' or condition == f'There is no semester {semester_number}. The maximum amount of semesters is 8.':
            Explanations.append(condition)
            return Explanations
        elif condition == f'{query_course_code} has already been taken in a past semester.':
            Explanations.append(condition)
            return Explanations
        
        else:

            # Check if the course is already in the current schedule and negate its variable and remove from true_lits
            for semester, courses in enumerate(schedules[current_schedule_index]):
                if query_course_code in courses:
                    var = [scheduler.course_vars[query_course_code]['semester_vars'][semester - scheduler.current_semester]]
                    # courses_in_query_already_scheduled.append(var)
                    updated_true_lits.remove(var)
                    neg_queries.append([-var[0]])

            if condition == True:  # Positive condition (course should be taken)
                if semester_number is not None:
                    pos_queries.append([query_var])
                    all_pos_query_courses.append((query_course_code, semester_number))
                else:
                    # Add an OR clause for the variable to be scheduled in any semester
                    OR_clause = [v for v in scheduler.course_vars[query_course_code]['semester_vars']]
                    pos_queries.append(OR_clause)
                # Check if the prerequisites of the course are already scheduled or in the query to be scheduled
                not_taken_prereqs = [c for c in scheduler.courses[query_course_code]['prerequisites'] if c not in scheduled_courses and c not in courses_in_query]
                if not_taken_prereqs:
                    Explanations.append(f"{query_course_code} cannot be scheduled because its prerequisite course(s) {', '.join(not_taken_prereqs)} has not been completed.")

            elif condition == False: # Negative condition (course should not be taken)
                if semester_number is not None:
                    var = [query_var]
                    neg_var = [-query_var]
                    if var in updated_true_lits:
                        updated_true_lits.remove(var)
                    if neg_var not in neg_queries:
                        neg_queries.append(neg_var)
                else:
                    # Add a negated AND clause for the variable to not be scheduled in any semester
                    AND_clause = [[-v] for v in scheduler.course_vars[query_course_code]['semester_vars']]
                    for v in AND_clause:
                        if v not in neg_queries:
                            neg_queries.append(v)

    
    Q = CNF(from_clauses = pos_queries.clauses + neg_queries.clauses)
    print(Q.clauses)


    # Construct the KB
    KB = [clause for clause in scheduler.cnf.hard + scheduler.cnf.soft]



    if Q.clauses:
        while True:
            if SAT(KB, updated_true_lits):
                if not SAT(KB + updated_true_lits, Q.clauses):
                    print("Query conflicts with the knowledge base.")
                    template_expl = explanation(scheduler, KB, updated_true_lits, Q.clauses)
                    Explanations.append(' '.join(template_expl))
                    return Explanations

                # elif SAT(KB + updated_true_lits, Q.negate(topv=scheduler.vpool.top).clauses) == False:
                #     print("Negated query is entailed")
                #     template_expl = explanation(scheduler, KB + updated_true_lits, Q.negate(topv=scheduler.vpool.top).clauses)
                #     Explanations.append(' '.join(template_expl))
                #     return Explanations
                else:
                    Explanations.append('The query does not conflict with the scheduling constraints, and thus it can be satisfied.')
                    return Explanations

            else:
                print("repairing...")
                KB = repair(KB, updated_true_lits)

    return Explanations





def explain_why_not_query(scheduler, schedules, current_schedule_index, true_lits, query_data):
    """ Contrastive Explanations: Why not course X in semester Y, ..."""

    scheduled_courses = [course for semester in schedules[current_schedule_index] for course in semester]
    updated_true_lits = copy.deepcopy(true_lits[current_schedule_index])

    explanations = []
    prior_query_vars = []
    pos_queries = []
    neg_queries = []
    all_pos_query_courses = []
    all_neg_query_courses = []

    for query_course_code, semester_number, condition, query_var in query_data:
        if condition:  # Positive condition (course should be taken)
            pos_queries.append([query_var])
            all_pos_query_courses.append((query_course_code, semester_number))
            query_prereqs = scheduler.courses[query_course_code]['prerequisites']
            query_prereqs_incomplete = []
            for q in query_prereqs:
                if q not in scheduled_courses:
                    query_prereqs_incomplete.append(q)
            
            if query_prereqs_incomplete:
                explanations.append(f"{query_course_code} cannot be scheduled in semester {semester_number + scheduler.current_semester + 1} because the prerequisite course(s) {', '.join(query_prereqs_incomplete)} has not been completed.")
         
            # Check if the query course has been scheduled in any other semester

            for semester, courses in enumerate(schedules[current_schedule_index]):
                if query_course_code in courses:
                    prior_query_vars.append([scheduler.course_vars[query_course_code]['semester_vars'][semester - scheduler.current_semester]])
                    break    
        else:
            all_neg_query_courses.append((query_course_code, semester_number))
            neg_queries.append([query_var])
    

    # Construct the knowledge base
    KB = scheduler.cnf
    wcnf = WCNF()
    for k in KB.soft + KB.hard:
        wcnf.append(k, weight=1)
    for l in updated_true_lits:
        wcnf.append(l)

    lbx = LBX(wcnf, use_cld=True, solver_name='g3')
    # Compute mcs and return the clauses
    mcs = lbx.compute()
    to_retract = [list(wcnf.soft[m - 1]) for m in mcs]
  
    # Construct the satisfiable knowledge base
    sat_kb = []
    if prior_query_vars:
        to_retract.append(prior_query_vars)
        for c in prior_query_vars:
            sat_kb.append([-c[0]])
            updated_true_lits.remove(c)

    
    if neg_queries:
        for q in neg_queries:
            if [-1*q[0]] in updated_true_lits:
                updated_true_lits.remove([-1*q[0]])
                updated_true_lits.append(q)
            sat_kb.append(q)

    for k in KB.soft + KB.hard + updated_true_lits:
        if k not in to_retract:
            sat_kb.append(k)

    s = Solver()
    s.append_formula(sat_kb)
    s.append_formula(pos_queries)
    sol = s.solve()
    # print(sol)
    if sol:
        if all_pos_query_courses:
            explanations.append(f"Course(s) {', '.join(course[0] for course in all_pos_query_courses)} can be scheduled in semester(s) {', '.join(str(course[1] + scheduler.current_semester + 1) for course in all_pos_query_courses)}.")
        elif all_neg_query_courses:
            explanations.append(f"Course(s) {', '.join(course[0] for course in all_neg_query_courses)} can be removed from semester(s) {', '.join(str(course[1] + scheduler.current_semester + 1) for course in all_neg_query_courses)}.")
    else:
        
        wcnf2 = WCNF()

        for c in sat_kb:
            wcnf2.append(c, weight=1)

        for l in updated_true_lits:
            wcnf2.append(l)
        
        
        q = CNF(from_clauses=pos_queries)
        # wcnf2.extend((q.negate(topv=scheduler.vpool.top).clauses))
        wcnf2.extend(q)



        mus_explanations = []
        count = 0
        max_count = 1
        MUS = OptUx(wcnf2, solver="MapleCM", unsorted=True)
        for mus in MUS.enumerate():
            expl  = [list(wcnf2.soft[m - 1]) for m in mus]
            mus_explanations.append(expl)
            count += 1
            if count == max_count:
                break
        print(mus_explanations)
        for expl in mus_explanations:
            temp = []
            for e in expl:
                for label in scheduler.templates:
                    if e in scheduler.templates[label]:
                        if label not in temp:
                            temp.append(label)
            temp = ' '.join(temp)
            explanations.append(temp)

    return explanations


def semantic_similarity(pre_processed_explanation, post_processed_explanation):
    model = SentenceTransformer("dmlls/all-mpnet-base-v2-negation", device='mps')
    # model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device='mps')

    model.similarity_fn_name = SimilarityFunction.COSINE

    #Compute embedding for both lists
    embedding_1= model.encode(pre_processed_explanation, device='mps')
    embedding_2 = model.encode(post_processed_explanation, device='mps')

    similarity = model.similarity(embedding_1, embedding_2)

    return similarity.item()
