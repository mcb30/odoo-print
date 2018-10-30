"""Main controller"""

from odoo import http
from odoo.addons.web import controllers


class Session(controllers.main.Session):
    """Session controller"""

    @http.route()
    def logout(self, *args, **kwargs):
        """Logout"""
        uid = http.request.session.uid
        if uid is not None:
            http.request.env['print.printer'].sudo(uid).clear_ephemeral()
        return super().logout(*args, **kwargs)
