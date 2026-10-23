Name and Surname: Maide Letswalo
Student ITS No: 0722993357
Qualification: BSC IN IT
Year of Study: 2
Semester:2
Assignment due date: 23 October 2026
Date submitted: 23 October 2026
Module: Programming 512

SMART CAMPUS RESOURCE BOOKING SYSTEM

1. HOW TO RUN THE PROGRAM

1. Ensure you have Python 3 installed on your computer.
2. Open a terminal or command prompt.
3. Navigate to the folder containing this file.
4. Run the following command:
   python smart_campus.py
   (Or run it directly from your Python IDE, such as IDLE, VS Code, or PyCharm).

2. DEFAULT LOGIN CREDENTIALS

The system automatically creates the following test accounts on first launch:

Role: Campus Administrator (Main Campus)
Username: admin_main
Password: admin123

Role: Campus Administrator (North Campus)
Username: admin_north
Password: admin123

Role: Campus Administrator (South Campus)
Username: admin_south
Password: admin123

Role: System Operator (Full Management Access)
Username: operator
Password: operator123

* Note: Lecturers can register their own accounts by clicking
the "Register Lecturer" button on the login screen.

3. DATABASE INFORMATION

The system uses an SQLite database named "smart_campus.db".
- It is created automatically in the same folder when you first run the app.
- All users, resources, and bookings are saved here.
- If you wish to reset the system to a clean state, simply delete
  the "smart_campus.db" file and run the program again.

USER GUIDE (HOW TO TEST THE SYSTEM)

A) AS A LECTURER (e.g., register a new account)
1. Click "Register Lecturer" on the login screen, create a username/password,
   select a campus, and log in.
2. Go to the "Book Resource" tab. You will see a list of available resources.
3. Enter a Date (YYYY-MM-DD), Start Time (HH:MM), and Duration (in hours).
4. Click "Refresh Availability" to check if the resource is free.
5. Click on a resource in the list to highlight it, then click
   "Book Selected Resource" to make a booking.
6. Go to the "My Bookings" tab to see your booking history.
7. To cancel a future booking, click on the row to highlight it and
   click "Cancel Selected Booking".

B) AS A CAMPUS ADMINISTRATOR (e.g., admin_main)
1. Log in. You are locked to your specific campus.
2. "Manage Resources" tab:
   - To ADD: Type a Code, Name, and Type, then click "Add".
   - To UPDATE: Click a resource in the list, change the text in the
     boxes above, and click "Update Selected".
   - To DELETE: Click a resource in the list and click "Delete Selected".
     (Note: You cannot delete a resource if it has active bookings).
3. "Availability Monitor" tab: Enter a date/time and click "Check Availability"
   to see usage trends and what is currently booked.
4. "Campus Bookings" tab: View all bookings made by lecturers on your campus.
5. "Campus Reports" tab: Click "Generate Campus Report" to see total bookings
   and the most popular resources.
C) AS A SYSTEM OPERATOR (e.g., operator)
1. Log in. You have access to all campuses (use the dropdown at the top).
2. "All Bookings" tab: View every booking across all campuses.
3. "All Resources" tab: View every resource across the institution.
4. "Cross-Campus Reports" tab: Click "Generate Cross-Campus Comparison"
   to see a report comparing usage, average durations, and the effect of
   different campus booking rules.
