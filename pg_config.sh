apt-get -qqy update
apt-get -qqy install postgresql python-psycopg2
apt-get -qqy install python-flask python-sqlalchemy
apt-get -qqy install python-pip
apt-get -qqy install git
apt-get -qqy install ruby-full
wget -qO- https://toolbelt.heroku.com/install-ubuntu.sh | sh
gem install foreman
pip install werkzeug==0.8.3
pip install Flask-Login==0.1.3
pip install SQLAlchemy-ImageAttach
pip install oauth2client
pip install requests
pip install httplib2
pip install redis
pip install passlib
pip install flask-httpauth
pip install flask-seasurf

vagrantTip="[35m[1mThe shared directory is located at /vagrant\nTo access your shared files: cd /vagrant(B[m"
echo -e $vagrantTip > /etc/motd
