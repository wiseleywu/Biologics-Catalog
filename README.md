# Biologics Catalog
A web application that serves as a catalog for antibody, cytotoxin, and antibody-drug conjugate available for request. In an ideal world, R&D division within a pharmaceutical company could use this to organize all samples they have developed that could be used internally (e.g. analytical, process development, crystallography, in-vitro studies, in-vivo studies, and more). Of course, we have Food & Drug Administration (FDA) in the real world that regulates electronic records from pharmaceutical companies, medical device manufacturers, biotech/biologics companies, and other FDA-regulated industries - this application is obviously not [Title 21 CFR Part 11 compliant][1] so it will not be suitable for their use. However, most real world application developed for these industries are usually difficult to use, unintuitive, and unappealing to end users, to say the least. This is my take of what a minimalist biologics catalog web application could look like - designed with the end users in mind to make it as easy to use as possible while having the look of a modern website/software most end users are accustomed to in this digital world.

## Overview
Biologics Catalog is a web application built with [Flask][2]. It provides a list of items within a variety of categories as well as provide a user registration and authentication system. Registered users will have the ability to post, edit and delete their own items.

The backend of this application uses Postgres Database to organize users and all the entries they have created. To interface between python and the database, [SQLAlchemy][3] and its Object Relational Mapper (ORM) is used to map python Classes to the database, allowing CRUD operations with simple python syntax instead of dense SQL commands. The application uses Oauth 2.0 to authenticate and authorize users via third party websites such as Google and Facebook; this enable new or returning users to login to the website securely without resorting to creating another new account and coming up with a complex password. User's credentials with Google/Facebook will be used to authenticate and authorize them when creating, updating, or deleting information from the web application. Biologics catalog also provides JSON and XML endpoints for sharing data with other websites.

## What's Included
- `database_setup.py` - This file included codes to setup the database schema via SQLAlchemy's ORM. There's also implementation for the JSON API endpoint
- `helper.py` - This file housed all the helper functions used by other files
- `initDB.py` - This file setup Postgres database and create a session with SQL Alchemy's ORM
- `populator.py` - Script used to populate the database with pred-defined users (including you!) and demo entries. You can modify the first user to yourself to simulate what it would look like to have several entries created by you in the application (Instrution below)
- `project.py` - The flask framework and its interface with the database (via ORM) and the html website template (via jinja2) are defined here
- `settings.py` - This file housed general settings for the web app, such as global constants, absolute path for storage/upload, credentials for Postgres database, and OAuth objects from Google/Facebook

## Front End
- [Bootstrap][4]
- [sortable][5]
- [jQuery][6]
- [TWBScolor][7]

## Back End
- [python-flask][2]
- [flask-seasurf][8]
- [python-psycopg2][9]
- [python-sqlalchemy][3]
- [SQLAlchemy-ImageAttach][10]
- [oauth2client][11]

## Endpoints
 - JSON
  - Access this from `/category/json` or `/category/lot/json`, where category could be antibody, cytotoxin, or adc
 - XML
  - Access this from `/category/xml` or `/category/lot/xml`, where category could be antibody, cytotoxin, or adc

## Instructions
- Clone this repository
- Install [Vagrant][12] and [VirtualBox][13]
- Optional to test out Google Oauth 2.0 Login
  - Create a new project from [Google Developers Console][14]. Go to API Manager -> Credentials in the Developers Console to create an OAuth client ID for web application use.
  - Add `http://localhost:5000` under "Authorized Javascript origins"
  - Add `http://localhost:5000/gconnect`, `http://localhost:5000/login`, and `http://localhost:5000/oauth2callback` under "Authorized redirect URIs"
  - Either Download and rename the JSON file from Google or change the `client_id` in [client_secrets.json](client_secrets.json) provided to the one you obtained above.
- Optional to test out Facebook Oauth 2.0 login
  - Create a new application from [Facebook for Developers][15] for website. Go to your app dashboard to obtain your App ID and App Secret.
  - Change the `app_id` and `app_secret` in [fb_client_secrets.json](fb_client_secrets.json) with the one you obtained above.
- Navigate to this directory in the terminal and enter `vagrant up` to initialize/power on the Vagrant virtual machine
- Enter `vagrant ssh` to log into the virtual machine
- Navigate to vagrant directory within the virtual machine by typing `cd /vagrant`
- (optional) Create a new user using `createUser()` in [vagrant/populator.py](populator.py) with your name, g-mail address, and a link of your profile picture
- (optional) Change absolute path on server or Postgres database credentials in [vagrant/settings.py](settings.py) if needed
- Run [vagrant/populator.py](populator.py) to populate database with pre-defined users and items
- Run [vagrant/project.py](project.py) and navigate to [http://localhost:5000/][16] in your browser
- Sign in with your google account at top right corner of the website. Once signed in, you will be able to see what you can and cannot modify on the website
- To test Facebook Sign in, either make sure your g-mail address is the same as your Facebook login or modify [vagrant/populator.py] (populator.py) with the proper credentials

[1]: http://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfcfr/CFRSearch.cfm?CFRPart=11
[2]: http://flask.pocoo.org/
[3]: http://www.sqlalchemy.org/
[4]: http://getbootstrap.com/
[5]: http://github.hubspot.com/sortable/
[6]: https://jquery.com/
[7]: http://work.smarchal.com/twbscolor/
[8]: https://flask-seasurf.readthedocs.org/en/latest/
[9]: http://initd.org/psycopg/
[10]: https://sqlalchemy-imageattach.readthedocs.org/en/0.9.0/
[11]: https://pypi.python.org/pypi/oauth2client
[12]: https://www.vagrantup.com/downloads.html
[13]: https://www.virtualbox.org/wiki/Downloads
[14]: https://console.developers.google.com/
[15]: https://developers.facebook.com/
[16]: http://localhost:5000/
