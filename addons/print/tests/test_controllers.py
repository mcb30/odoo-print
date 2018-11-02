"""Printing controller tests"""

from contextlib import contextmanager
from odoo.tests import common


@common.at_install(False)
@common.post_install(True)
class TestController(common.HttpCase):
    """Printing controller tests"""

    @contextmanager
    def env_test(self):
        saved_cr = self.cr
        saved_env = self.env
        try:
            with self.registry.cursor() as cr:
                self.cr = cr
                self.env = self.env(cr)
                yield
        finally:
            self.env = saved_env
            self.cr = saved_cr

    def setUp(self):
        super().setUp()
        with self.env_test():

            # Create user
            User = self.env['res.users']
            self.user_alice = User.create({
                'name': "Alice",
                'login': "alice",
                'password': "password",
            })

            # Create printers
            Printer = self.env['print.printer']
            self.printer_inkjet = Printer.create({
                'name': "Inkjet",
                'is_ephemeral': True,
            })
            self.printer_laser = Printer.create({
                'name': "Laser",
                'is_ephemeral': False,
            })

            # Acquire session cookie
            self.authenticate("alice", "password")

    def test01_logout_ephemeral(self):
        """Test clearing ephemeral printers on logout"""
        with self.env_test():
            self.printer_inkjet.sudo(self.user_alice).set_user_default()
        self.assertIn(self.printer_inkjet, self.user_alice.printer_ids)
        self.url_open('/web/session/logout')
        self.env.clear()
        self.assertNotIn(self.printer_inkjet, self.user_alice.printer_ids)

    def test02_logout_non_ephemeral(self):
        """Test not clearing non-ephemeral printers on logout"""
        with self.env_test():
            self.printer_laser.sudo(self.user_alice).set_user_default()
        self.assertIn(self.printer_laser, self.user_alice.printer_ids)
        self.url_open('/web/session/logout')
        self.env.clear()
        self.assertIn(self.printer_laser, self.user_alice.printer_ids)
