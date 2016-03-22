#!/usr/bin/env python2.7

import datetime
import string
import random
import os
import json
import re
import urllib
import tornado.web
from passlib.hash import pbkdf2_sha256

import handler
import settings
import db
import util

class InviteHandler(handler.BaseHandler):
    def get(self):
        self.render("invite.html")
        return
        if self.current_user is not None:
            self.render("invite.html")
        self.render("login.html")

    def post(self):
        email = self.get_argument('email', None)
        if not re.match("^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]+$", email, flags = re.IGNORECASE):
            self.render("invite.html", message = "Please enter a valid email address.")
        else:
            with db.getCur() as cur:
                code = util.randString(32)
                cur.execute("INSERT INTO VerifyLinks (Id, Email, Expires) VALUES (?, ?, ?)", (code, email, (datetime.date.today() + datetime.timedelta(days=7)).isoformat()))

            util.sendEmail(email, "Your SeattleMahjong Account",
                    "<p>You've been invited to SeattleMahjong\n<br />\
                    Click <a href=\"http://" +  self.request.host + "/verify/" + code + "\">this</a> link to accept the invite and register an account or copy and paste the following into your URL bar:<br />http://" +  self.request.host + "/verify/" + code + "</p>\n" +
                    "<p>If you believe you received this email in error, it can be safely ignored. It is likely a user simply entered your email by mistake.</p>")

            self.render("message.html", message = "Invite sent. It will expire in 7 days.", title = "Invite")
class VerifyHandler(handler.BaseHandler):
	def get(self, q):
		with db.getCur() as cur:
			cur.execute("SELECT Email FROM VerifyLinks WHERE Id = ? AND Expires > datetime('now')", (q,))

			if cur.rowcount == 0:
				self.redirect("/")
				return

			email = cur.fetchone()[0]

		self.render("verify.html", email = email, id = q)
	def post(self, q):
		email = self.get_argument('email', None)
		password = self.get_argument('password', None)
		vpassword = self.get_argument('vpassword', None)

                if email is None or password is None or vpassword is None:
                    self.render("verify.html", email = email, id = q, message = "You must enter an email, pasword, and repeat your password")
                    return
                if password != vpassword:
                    self.render("verify.html", email = email, id = q, message = "Your passwords didn't match")
                    return

		with db.getCur() as cur:
                        passhash = pbkdf2_sha256.encrypt(password)

                        cur.execute("INSERT INTO Users (Email, Password) VALUES (?, ?)", (email, passhash))
                        self.set_secure_cookie("user", str(cur.lastrowid))
                        cur.execute("DELETE FROM VerifyLinks WHERE Id = ?", (q,))

		self.redirect("/")

class LoginHandler(handler.BaseHandler):
    def get(self):
        if self.current_user is not None:
            self.render("message.html", message = "You're already logged in, would you like to <a href=\"/logout\">Logout?</a>")
            return

        self.render("login.html")

    def post(self):
        email = self.get_argument('email', None)
        password = self.get_argument('password', None)
        next = self.get_argument("next", "/")

        if not email or not password:
            self.render("login.html", message = "Please enter an email and password")
            return

        with db.getCur() as cur:
            cur.execute("SELECT Id, Password FROM Users WHERE Email = ?", (email,))

            row = cur.fetchone()
            if row is not None:
                result = row[0]
                passhash = row[1]

                if pbkdf2_sha256.verify(password, passhash):
                    self.set_secure_cookie("user", str(result))
                    cur.execute("SELECT EXISTS(SELECT * FROM Admins WHERE Id = ?)", (result,))
                    if cur.fetchone()[0] == 1:
                        self.set_secure_cookie("admin", "1")

                if result != None:
                    self.redirect(next)
                    return
        self.render("login.html", message = "Incorrect email and password")

class LogoutHandler(handler.BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.clear_cookie("admin")
        self.redirect("/")
