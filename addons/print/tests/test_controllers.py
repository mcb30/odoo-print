"""Printing controller tests"""

from .common import PrinterHttpCase


class TestController(PrinterHttpCase):
    """Printing controller tests"""

    def setUp(self):
        super().setUp()

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

    def test01_logout_ephemeral(self):
        """Test clearing ephemeral printers on logout"""
        self.authenticate("alice", "password")
        self.printer_inkjet.sudo(self.user_alice).set_user_default()
        self.assertIn(self.printer_inkjet, self.user_alice.printer_ids)
        self.url_open('/web/session/logout')
        self.assertNotIn(self.printer_inkjet, self.user_alice.printer_ids)

    def test02_logout_non_ephemeral(self):
        """Test not clearing non-ephemeral printers on logout"""
        self.authenticate("alice", "password")
        self.printer_laser.sudo(self.user_alice).set_user_default()
        self.assertIn(self.printer_laser, self.user_alice.printer_ids)
        self.url_open('/web/session/logout')
        self.assertIn(self.printer_laser, self.user_alice.printer_ids)

    def test03_logout_unauthenticated(self):
        """Test logout from a non-authenticated user"""
        self.url_open('/web/session/logout')
