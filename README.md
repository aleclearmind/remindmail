# remindmail

This is a very simple script that sends you an e-mail if you don't get an answer to an e-mail within a deadline.

It is designed to integrate with the `exim` MTA.

It can be seen as a self-hosted version of [followupthen.com](https://www.followupthen.com).

# Usage

1. Configure `remindmail`
2. When you want to be reminded about an unanswered e-mail, add in Bcc `rm.*@mydomain.com`, where `*` is a time span from now.
   The time span can be `2s` for "two seconds" or `3d` for "three days" (see [pytimeparse](https://pypi.org/project/pytimeparse/)).
   If you don't get an answer by then, you will receive an answer to that e-mail to remind you that you need an answer.

# How does this work?

The key idea is to have your MTA to feed to the script all the incoming and outgoing e-mail.
If an e-mail is addressed to `rm.2d@mydomain.com`, the `Message-ID` of the e-mail is recorded in a database along with a deadline (in this case, two days from now).

If an e-mail has a `In-Reply-To` header which matches one of the `Message-ID`s recorded in the databases, the corresponding entry is removed.

If after the chosen deadline, no answer has been received, a notification e-mail is sent to the sender.

# Configuration

In order to use `remindmail` you need to 1) configure `exim` so that feeds all the e-mails to the script and 2) set up a cron job to send out notifications.

## Configuring `exim`

```
git clone https://github.com/aleclearmind/remindmail.git /etc/exim4/remindmail/
```

This script is designed to be run as an "antivirus" from exim.
Uncomment the [`av_scanner`](https://www.exim.org/exim-html-current/doc/html/spec_html/ch-content_scanning_at_acl_time.html) directive in your `exim.conf` file as follows:

```
av_scanner = cmdline:/etc/exim4/remindmail/remindmail.py \
                         --db /var/mail/remindmail.db \
                         --domain mydomain.com \
                         %s \
                    :nopenope:nopenope
```

Make sure `/var/mail/remindmail.db` can be read and written by the `exim`'s daemon user.
Note that also the containing directory needs to be writeable, since the `sqlite` creates lock files.

You should also what follows:

```
acl_smtp_data = acl_check_data

acl_check_data:
  deny    malware    = *
          message    = This message contains a virus ($malware_name).
  accept
```

This enables the `av_scanner`, which is otherwise ineffective.
Note however that this script will always return true.
Therefore, it will never block any e-mail.

## Configuring notifications

Simply add a cron job:

```
cat > /etc/cron.hourly/remindmail <<eof
#!/bin/bash
/etc/exim4/remindmail/remindmail.py \
    --domain mydomain.com \
    --db /var/mail/remindmail.db \
    --check
eof
chmod +x /etc/cron.hourly/remindmail
```

# Notes

* The recipient of the e-mail won't know anything about `remindmail`, as long as you employ the `Bcc` header.
* The chosen SMTP server for sending e-mail is supposed to authorize any e-mail.
  This makes sense if you have a rule to accept any e-mail from 127.0.0.1 and the script is running on the same machine as the SMTP server.
* The database only records three things: the sender who wants to be notified, the `Message-ID` and the deadline.
  Nothing else is recorded.

# Debugging

You can print the database contents as follows:

```
/etc/exim4/remindmail/remindmail.py \
    --domain mydomain.com \
    --db /var/mail/remindmail.db \
    --print-db
```
