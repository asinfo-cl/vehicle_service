from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderRepair(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Client',
        })
        cls.vehicle = cls.env['workshop.vehicle'].create({
            'license_plate': 'XYZ789',
            'brand': 'Honda',
            'model_name': 'Civic',
            'partner_id': cls.partner.id,
        })

    def test_repair_order_creation(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'service_type': 'repair',
            'vehicle_id': self.vehicle.id,
        })
        self.assertEqual(order.service_type, 'repair')
        self.assertEqual(order.vehicle_id, self.vehicle)
        self.assertEqual(order.repair_status, 'diagnosis')

    def test_repair_sections_created(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'service_type': 'repair',
            'vehicle_id': self.vehicle.id,
        })
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertGreater(len(sections), 0)
        section_categories = sections.mapped('line_category')
        self.assertIn('labor', section_categories)
        self.assertIn('parts', section_categories)
