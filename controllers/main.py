from odoo import http


class VehicleServiceController(http.Controller):

    @http.route('/vehicle_service/health', type='json', auth='user')
    def health_check(self):
        return {'status': 'ok'}
