from scheduler import *
from pysat.solvers import Solver
import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog
from explainer import contrastive_explanations, post_process_explanation, process_query, post_process_query, semantic_similarity, repair
from pysat.examples.optux import OptUx
from pysat.examples.lbx import LBX
from pysat.formula import IDPool, WCNF, CNF
from pysat.examples.rc2 import RC2
from pysat.card import CardEnc, EncType

import copy
from utils import *


'''------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------'''



# Load course data
core_courses_file = './files/core_courses.json'
cs_electives_file = './files/CS_electives.json'
sciences_electives_file = './files/sciences_electives.json'
social_electives_file = './files/social_electives.json'
methods_electives_file = './files/methods_electives.json'
systems_electives_file = './files/systems_electives.json'
user_input_file = './files/user_input.json'

scheduler = CourseScheduler(core_courses_file, methods_electives_file, systems_electives_file, cs_electives_file, sciences_electives_file, social_electives_file, user_input_file)
schedules, models, true_lits = scheduler.solve()
current_schedule_index = 0
current_explanation_index = 0





'''GUI'''

window = ttk.Window(title="Course Scheduler", themename="pulse")
# solar

# Create a frame for the schedule grid
schedule_frame = ttk.Frame(window, padding=10)
schedule_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))

# Function to export the schedule to a file
def export_schedule():
    file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
    if file_path:
        with open(file_path, 'w') as file:
            for i in range(scheduler.total_semesters):
                file.write(f"Semester {i + 1}:\n")
                if str(i + 1) in scheduler.taken_courses:
                    for course in scheduler.taken_courses[str(i + 1)]:
                        file.write(f"- {course}\n")
                elif i >= scheduler.current_semester - 1:
                    for course in schedule[i]:
                        file.write(f"- {course}\n")
                file.write("\n")

# # Create a frame for the export button
export_frame = ttk.Frame(window, padding=10)
export_frame.grid(row=1, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))

# Configure the styles for buttons and labels
style = ttk.Style()
style.configure("Green.TButton", background="green", foreground="white")
style.configure("Green.TLabel", background="green", foreground="white")
style.configure("Export.TButton", background="blue", foreground="white")
style.configure("Submit.TButton", background="orange", foreground="black")
style.configure("Red.TButton", background="red", foreground="white")
style.configure("Blue.TButton", background="blue", foreground="white") 
style.configure("Gray.TButton", background="gray", foreground="white")


# # Create a button to export the schedule
# export_button = ttk.Button(export_frame, text="Export Schedule", command=export_schedule, style="Export.TButton")
# export_button.pack(pady=10)


# Function to display course details
# def display_course_details(course):
#     details_text.delete(1.0, tk.END)
#     details_text.insert(tk.END, f"Course: {course}\n")
#     details_text.insert(tk.END, f"Credit Units: {scheduler.courses[course]['credit_units']}\n")
#     details_text.insert(tk.END, f"Prerequisites: {', '.join(scheduler.courses[course]['prerequisites'])}\n")
def display_course_details(event, course):
    tooltip_label.configure(text=f"Course: {course}\nCredit Units: {scheduler.courses[course]['credit_units']}\nPrerequisites: {', '.join(scheduler.courses[course]['prerequisites'])}")
    tooltip.deiconify()
    tooltip.geometry(f"+{event.x_root+10}+{event.y_root+10}")

def hide_course_details(event):
    tooltip.withdraw()


# Create labels for all semesters
for i in range(scheduler.total_semesters):    
    semester_label = ttk.Label(schedule_frame, text=f"Semester {i + 1}", font=("Arial", 15, "bold", "underline"))
    semester_label.grid(row=0, column=i, padx=10, pady=5)





def previous_schedule():
    global current_schedule_index
    current_schedule_index = (current_schedule_index - 1) % len(schedules)
    update_schedule_display()
    update_navigation_buttons()


def next_schedule():
    global current_schedule_index
    # print("Next Schedule button clicked")
    # print("Current schedule index before:", current_schedule_index)
    current_schedule_index = (current_schedule_index + 1) % len(schedules)
    # print("Current schedule index after:", current_schedule_index)
    update_schedule_display()
    update_navigation_buttons()

def update_navigation_buttons():
    previous_schedule_button.config(state=tk.NORMAL if current_schedule_index > 0 else tk.DISABLED)
    next_schedule_button.config(state=tk.NORMAL if current_schedule_index < len(schedules) - 1 else tk.DISABLED)

def update_schedule_display():
    # print("Updating schedule display")
    for widget in schedule_frame.winfo_children():
        if isinstance(widget, ttk.Button) and widget.cget("text") not in [f"Semester {i+1}" for i in range(scheduler.total_semesters)]:
            widget.destroy()
    
    for i in range(scheduler.total_semesters):
        semester = str(i + 1)
        if semester in scheduler.taken_courses:
            for j, course in enumerate(scheduler.taken_courses[semester]):
                course_button = ttk.Button(schedule_frame, text=course, style="Gray.TButton")
                # course_button = tk.Button(schedule_frame, text=course, bg="green", fg="white", relief=tk.RIDGE, borderwidth=2)
                course_button.bind("<Enter>", lambda event, c=course: display_course_details(event, c))
                course_button.bind("<Leave>", hide_course_details)
                course_button.grid(row=j+1, column=i, padx=10, pady=5)
        elif i >= scheduler.current_semester - 1:

            # print(f"Displaying courses for Semester {i+1}")
            for j, course in enumerate(schedules[current_schedule_index][i]):
                # print(f"Displaying course: {course}")
                course_button = ttk.Button(schedule_frame, text=course, style="Green.TButton")
                course_button.bind("<Enter>", lambda event, c=course: display_course_details(event, c))
                course_button.bind("<Leave>", hide_course_details)
                course_button.grid(row=j+1, column=i, padx=10, pady=5)

update_schedule_display()



previous_schedule_button = ttk.Button(export_frame, text="Previous Schedule", command=previous_schedule)
previous_schedule_button.pack(side=tk.LEFT, padx=(0, 10))

next_schedule_button = ttk.Button(export_frame, text="Next Schedule", command=next_schedule)
next_schedule_button.pack(side=tk.LEFT)
update_navigation_buttons()

# Create a frame for course details and query
details_frame = ttk.Frame(window, padding=5)
details_frame.grid(row=2, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))

# # Create a text widget to display course details
# details_text = tk.Text(details_frame, width=5, height=5)
# details_text.pack(fill=tk.BOTH, expand=True)

# Create a tooltip window for displaying course details
tooltip = tk.Toplevel(window)
tooltip.withdraw()
tooltip.overrideredirect(True)

# Create a label to display course details in the tooltip
tooltip_label = ttk.Label(tooltip, text="", wraplength=300)
tooltip_label.pack(padx=10, pady=10)



# Create a frame for query-related widgets
query_frame = ttk.Frame(details_frame)
query_frame.pack(fill=tk.Y, expand=True)

# # Create a label and text input field for queries
# query_label = ttk.Label(query_frame, text="Enter your query:")
# query_label.pack(side=tk.LEFT, padx=(0, 10))
# query_input = ttk.Entry(query_frame, width=50)
# query_input.pack(side=tk.LEFT)

# Create a label and text input field for queries
query_label = ttk.Label(query_frame, text="Please enter your query:", font=("Arial", 12, "bold"))
query_label.pack(anchor=tk.W)
query_input = ttk.Entry(query_frame, width=60)
query_input.pack(fill=tk.X)



# Create a text widget to display explanations
explanation_text = tk.Text(details_frame, width=80, height=10, font=("Arial", 14))
explanation_text.pack(fill=tk.BOTH, expand=True)
explanation_text.explanations = []  # Initialize the explanations attribute

# Create a frame for the semantic similarity button
similarity_frame = ttk.Frame(details_frame)
similarity_frame.pack(fill=tk.X, padx=5, pady=(0, 5))



def update_explanation_display():
    explanation_text.delete(1.0, tk.END)
    if explanation_text.explanations:
        explanation = explanation_text.explanations[current_explanation_index]
        explanation_text.insert(tk.END, explanation)
    else:
        explanation_text.insert(tk.END, "No explanations found.")


# def previous_explanation():
#     global current_explanation_index
#     current_explanation_index = (current_explanation_index - 1) % len(explanation_text.explanations)
#     update_explanation_display()
#     update_explanation_buttons()


# def next_explanation():
#     global current_explanation_index
#     current_explanation_index = (current_explanation_index + 1) % len(explanation_text.explanations)
#     update_explanation_display()
#     update_explanation_buttons()


# def submit_query():
#     query = query_input.get()
#     explanations = explain_why_not_query(scheduler, schedules, true_lits, query)
#     explanation_text.delete(1.0, tk.END)
#     if explanations:
#         post_processed_explanations = [post_process_explanation("\n".join(exp), schedules[current_schedule_index], scheduler.courses) for exp in explanations]
#         # non_processed_explanations = [exp for exp in explanations]
#         explanation_text.explanations = post_processed_explanations
#         # explanation_text.explanations = non_processed_explanations
#         explanation_text.insert(tk.END, post_processed_explanations[0])
#         current_explanation_index = 0
#     else:
#         explanation_text.insert(tk.END, "No explanations found.")
#         explanation_text.explanations = []
#     update_explanation_buttons()

# Create a frame for confirmation buttons
confirmation_frame = ttk.Frame(details_frame)
confirmation_frame.pack(fill=tk.X, padx=5, pady=(0, 5))


def submit_query():
    query = query_input.get()
    extracted_info = process_query(scheduler, schedules[current_schedule_index], query)
    query_data = post_process_query(scheduler, extracted_info)
    print(query_data)

    # Display the extracted query information to the user for verification
    invalid_query = False
    verification_text = ""
    for course_code, semester_number, condition, query_var in query_data:
        if condition != True and condition != False:
            # print(f"Wrong query: {condition}")
            verification_text += f"Invalid query: {condition} Please type another query.\n"
            invalid_query = True
        else:
            
            verification_text += "Please confirm that this is the query you asked:\n"
            verification_text += f"You'd like to see if course {course_code} can be {'added to' if condition else 'removed from'} semester {semester_number + scheduler.current_semester + 1 if semester_number is not None else 'any'}\n"
    
    # Display the verification text in the explanation text widget
    explanation_text.delete(1.0, tk.END)
    explanation_text.insert(tk.END, verification_text)
    
    # Remove existing confirmation buttons if any
    confirm_button = None
    reject_button = None
    for widget in confirmation_frame.winfo_children():
        if widget.winfo_class() == 'TButton':
            if widget['text'] == 'Confirm':
                confirm_button = widget
            elif widget['text'] == 'Reject':
                reject_button = widget

    # Remove the "Semantic Similarity" button
    for widget in similarity_frame.winfo_children():
        widget.destroy()
    
    if not invalid_query:
        if confirm_button is None:
            # Add button for user confirmation
            confirm_button = ttk.Button(confirmation_frame, text="Confirm", command=lambda: confirm_query(query,query_data), style="Red.TButton")
            confirm_button.pack(side=tk.LEFT, padx=(0, 10))
        
        if reject_button is None:
            # Add button for user rejection
            reject_button = ttk.Button(confirmation_frame, text="Reject", command=reject_query, style="Red.TButton")
            reject_button.pack(side=tk.LEFT)
    else:
        # Remove confirm and reject buttons if the query is invalid
        if confirm_button:
            confirm_button.destroy()
        if reject_button:
            reject_button.destroy()

    

def confirm_query(query, query_data):
    global current_schedule_index

    explanations = contrastive_explanations(scheduler, schedules, current_schedule_index, true_lits, query_data)
    print(explanations)
    explanation_text.delete(1.0, tk.END)
    if explanations:
        post_processed_explanations = [post_process_explanation(explanations, query, schedules[current_schedule_index], scheduler.courses)]
        explanation_text.explanations = explanations  # Store the pre-processed explanations
        explanation_text.insert(tk.END, post_processed_explanations[0])
        current_explanation_index = 0
   
        # Remove existing widgets in the similarity frame
        for widget in similarity_frame.winfo_children():
            widget.destroy()
        
        # Create the "Semantic Similarity" button and score label
        similarity_button = ttk.Button(similarity_frame, text="Semantic Similarity", command= lambda: calculate_semantic_similarity(explanations[current_explanation_index], post_processed_explanations), style="Blue.TButton")
        similarity_button.pack(side=tk.LEFT)
       
        
    else:
        explanation_text.insert(tk.END, "No explanations found.")
        explanation_text.explanations = []
        
        # Remove the "Semantic Similarity" button if no explanation is found
        for widget in similarity_frame.winfo_children():
            widget.destroy()
    
    # Remove the "Confirm" and "Reject" buttons
    for widget in confirmation_frame.winfo_children():
        if widget.winfo_class() == 'TButton' and widget['text'] in ['Confirm', 'Reject']:
            widget.destroy()

def calculate_semantic_similarity(pre_processed_explanation, post_processed_explanation):

    similarity = semantic_similarity(pre_processed_explanation, post_processed_explanation)
    
    # Remove existing similarity label if any
    for widget in similarity_frame.winfo_children():
        if widget.winfo_class() == 'TLabel':
            widget.destroy()
    
    # Create the similarity score label
    similarity_label = ttk.Label(similarity_frame, text=f"Score: {similarity:.2f}")
    similarity_label.pack(side=tk.LEFT, padx=(10, 0))


def reject_query():
    # Clear the query input field and explanation text widget
    query_input.delete(0, tk.END)
    explanation_text.delete(1.0, tk.END)
    explanation_text.explanations = []
    
    # Remove the "Semantic Similarity" button
    for widget in similarity_frame.winfo_children():
        if widget.winfo_class() == 'TButton' and widget['text'] == 'Semantic Similarity':
            widget.destroy()
    
    # Remove the "Confirm" and "Reject" buttons
    for widget in confirmation_frame.winfo_children():
        if widget.winfo_class() == 'TButton' and widget['text'] in ['Confirm', 'Reject']:
            widget.destroy()



# Create a button to submit the query
submit_button = ttk.Button(query_frame, text="Submit Query", command=submit_query, style="Submit.TButton")
submit_button.pack(pady=(10, 0))



# previous_explanation_button = ttk.Button(details_frame, text="Previous Explanation", command=previous_explanation)
# previous_explanation_button.pack(side=tk.LEFT, padx=(0, 10))
# next_explanation_button = ttk.Button(details_frame, text="Next Explanation", command=next_explanation)
# next_explanation_button.pack(side=tk.LEFT)




# Start the main event loop
window.mainloop()