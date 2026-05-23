from odoo import http


class VehicleServiceController(http.Controller):

    @http.route('/vehicle_service/health', type='jsonrpc', auth='user', methods=['POST'])
    def health_check(self):
        return {'status': 'ok'}
