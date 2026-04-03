git clone https://www.github.com/odoo/odoo --depth 1 --branch 19.0 /opt/odoo19/odoo
cd /opt/odoo19
python3 -m venv odoo19-venv
source odoo19-venv/bin/activate
pip3 install wheel
pip3 install -r odoo/requirements.txt
deactivate
mkdir /opt/odoo19/odoo-custom-addons
exit
