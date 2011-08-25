ux.vumi.org
===========

Install the dependencies for fabric, the tool used for deploying::

    $ virtualenv --no-site-packages ve
    $ source ve/bin/activate
    (ve)$ pip install -r requirements.pip

After that just run to update the code on the server from the GitHub repository::

    $ ./deploy.sh