# -*- coding: utf-8 -*-

import datetime, os, json, smtplib, uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from workers import worker
import pycamunda.variable
import pycamunda.processdef


from dotenv import load_dotenv, dotenv_values 
# loading variables from .env file
load_dotenv() 
url = os.getenv('ENDPOINT')
start_instance = pycamunda.processdef.StartInstance(url=url, key=os.getenv('PROCESS_KEY_ID'))
os.environ['NO_PROXY'] = url

## Configure Gemini
import google.generativeai as genai
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# Connect database
import sqlite3
con = sqlite3.connect("ticket.db")  
cur = con.cursor()


def send_email(subject: str, body: str, to_email: str, path_to_file: str=""):
    from_email = os.getenv('EMAIL')
    password = os.getenv('PASS')
    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    host = 'smtp.office365.com'
    port = 587

    # Add body to email
    message.attach(MIMEText(body, "plain"))
    if path_to_file:
        with open(path_to_file,'rb') as file:
            # Attach the file with filename to the email
            message.attach(MIMEApplication(file.read(), Name="file.ext"))

    # Connect to the server and send email
    with smtplib.SMTP(host , port) as server:
        server.starttls()
        server.login(from_email, password)
        server.sendmail(from_email, to_email, message.as_string())



# Define a custom function to serialize datetime objects 
def serialize_datetime(obj): 
    if isinstance(obj, datetime.datetime): 
        return obj.isoformat() 
    raise TypeError("Type not serializable") 



departments = {
    'dpm1': 'Department 1',
    'dpm2': 'Department 2',
    'dpm3': 'Department 3',
    'dpm4': 'Department 4',
}



def rejectRequest(name, email: str, reasonsForRejected, dpm):
    ticket_id = str(uuid.uuid4())
    cur.execute(f"""
        INSERT INTO request VALUES 
            ('{ticket_id}', '{name.value}', '{dpm.value}', '{email.value}') 
    """)
    con.commit()
    
    subject = f"[Rejected] Request: {ticket_id}"
    
    response =  model.generate_content(f"""
    Viết một email từ Department 5 thể hiện lý do từ chối yêu cầu Thẩm định cho phòng ban {departments[dpm.value]} của PVN.
    Những lý do được từ chối như sau:
    {reasonsForRejected.value}
    Không được bổ sung bất kỳ lý do nào khác ngoài những lý do đã cung cấp.
    Yêu cầu phòng ban hoặc người đại diện {name.value} thực hiện lại quy trình Yêu cầu Thẩm định.
    """)

    send_email(subject, response.text, to_email=email.value)

    print("Send rejection email success")
    
    cur.execute(f"""
        INSERT INTO ticket VALUES 
            ('{ticket_id}', 'rejected', '{reasonsForRejected.value}', '{json.dumps(datetime.datetime.now(), default=serialize_datetime)}')
    """)
    con.commit()

    return {}



def acceptRequest(name, email: str, dpm):
    ticket_id = str(uuid.uuid4())

    cur.execute(f"""
        INSERT INTO request VALUES 
            ('{ticket_id}', '{name.value}', '{dpm.value}', '{email.value}') 
    """)
    con.commit()

    subject = f"[Accepted] Request ID: {ticket_id}"
    response =  model.generate_content(f"""
    Viết một email từ Department 5 thể hiện đồng ý thực hiện yêu cầu Thẩm định cho phòng ban {departments[dpm.value]} của PVN.
    Yêu cầu phòng ban hoặc người đại diện {name} tiếp tục các quy trình tiếp theo.
    """)

    send_email(subject, response.text, to_email=email.value)

    print("Send acceptance email success")

    cur.execute(f"""
        INSERT INTO ticket VALUES 
            ('{ticket_id}', 'accepted', NULL, '{json.dumps(datetime.datetime.now(), default=serialize_datetime)}')
    """)
    con.commit()

    return {}


if __name__ == '__main__':

    worker_id = '1'

    for _ in range(3):
        start_instance()

    worker = worker.Worker(url=url, worker_id=worker_id)
    worker.subscribe(
            topic='rejectRequest',
            func=rejectRequest,
            variables=['email', 'name', 'reasonsForRejected', 'dpm']
        )

    worker.subscribe(
            topic='acceptRequest',
            func=acceptRequest,
            variables=['email', 'name', 'dpm']
        )

    worker.run()