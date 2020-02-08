#!/usr/bin/python3

from glob import glob
import os
import argparse
import sys
import sqlite3
import pytimeparse
from datetime import datetime
import email
from email.parser import BytesParser, Parser
from email.policy import default
from email.message import EmailMessage
import smtplib

database_path = ""
domain = ""
mx = ""
clean_db = True

def connect():
    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS messages(sender TEXT, message_id TEXT, deadline INTEGER)")
    return (connection, cursor)

def print_db():
    connection, cursor = connect()

    # Look for expired records
    now = int(datetime.now().timestamp())
    results = cursor.execute("SELECT sender, message_id, deadline FROM messages")

    for (sender, message_id, deadline) in results:
        print("{} wants an answer to {} within {}{}".format(sender,
                                                            message_id,
                                                            str(datetime.fromtimestamp(deadline)),
                                                            " (expired)" if deadline < now else ""))

    connection.close()

def check():
    connection, cursor = connect()

    # Look for expired records
    now = int(datetime.now().timestamp())
    results = cursor.execute("SELECT sender, message_id FROM messages WHERE deadline < ?", (now, ))

    # Send an e-mail for each record
    smtp = smtplib.SMTP(mx)
    for (sender, message_id) in results:
        message = EmailMessage()
        message["Subject"] = "You were waiting for a response to this message"
        message["From"] = "rm@" + domain
        message["To"] = sender
        message["In-Reply-To"] = message_id
        message["Date"] = email.utils.formatdate()
        message.set_content(message["Subject"])
        smtp.send_message(message)
    smtp.quit()

    if clean_db:
        # Purge the DB
        cursor.execute("DELETE FROM messages WHERE deadline < ?", (now, ))
        connection.commit()

    connection.close()

def record(sender, message_id, span):
    assert message_id and sender

    connection, cursor = connect()

    # Parse the time span
    span = pytimeparse.parse(span)
    now = int(datetime.now().timestamp())
    deadline = now + span

    cursor.execute("""INSERT INTO messages(sender, message_id, deadline)
                      VALUES(?, ?, ?)""", (sender, message_id, deadline))

    connection.commit()
    connection.close()

def answered(message_id):
    assert message_id

    if clean_db:
        # Purge entries related to message_id
        connection, cursor = connect()
        cursor.execute("""DELETE FROM messages WHERE message_id = ?""", (message_id, ))
        connection.commit()
        connection.close()

def parse_email(path):
    # If path is a directory, focus on the only *.eml file in there
    if os.path.isdir(path):
        results = glob(os.path.join(path, "*.eml"))
        if len(results) != 1:
            return
        path = results[0]

    # Read the .eml file
    with open(path) as file:
        text = file.read()

    # Inform the parser that X-Envelope-To contains a list of addresses
    default.header_factory.map_to_type(name="X-Envelope-To", cls=email.headerregistry.AddressHeader)

    # Collect the relevant pieces
    message = Parser(policy=default).parsestr(text)
    message_id = message["Message-ID"]
    envelope_to = message["X-Envelope-To"]
    sender = message["From"]

    # The sender must be from the chosen domain
    if (sender
        and sender.addresses[0].domain == domain
        and envelope_to
        and message_id):

        # Check if any address in X-Envelope-To has an address rm.*@domain
        for address in envelope_to.addresses:
            prefix = "rm."
            if (address.domain == domain
                and address.username.startswith(prefix)):
                # OK, record the request in the DB
                record(sender, message_id, address.username[len(prefix):])

    # If we have the In-Reply-To, purge from the DB notifications related to
    # that message
    in_reply_to = message["In-Reply-To"]
    if in_reply_to:
        answered(in_reply_to)

def main():
    parser = argparse.ArgumentParser(description="Remind the e-mail.")
    parser.add_argument("--check", action="store_true", help="Send e-mails.")
    parser.add_argument("--print-db", action="store_true", help="Send e-mails.")
    parser.add_argument("--no-clean-db", action="store_true", help="Do not clean the DB after sending e-mails. Use this for testing purposes.")
    parser.add_argument("--domain", default="localhost", help="Domain to monitor.")
    parser.add_argument("--db", default="/tmp/remindmail.db", help="Sqlite database to employ.")
    parser.add_argument("--mx", default="", help="SMTP server.")
    parser.add_argument("message_dir", metavar="MESSAGE_DIR", nargs="?", help="an .eml file or a directory containing an .eml file.")
    args = parser.parse_args()

    global clean_db
    clean_db = not args.no_clean_db

    global domain
    domain = args.domain

    global mx
    mx = args.mx if args.mx else domain

    global database_path
    database_path = args.db

    assert args.print_db + args.check <= 1

    if args.print_db:
        print_db()
    elif args.check:
        check()
    else:
        parse_email(args.message_dir)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        import traceback
        traceback.print_exc()

    # This program must *never* fail or the mail won't go through
    sys.exit(0)
