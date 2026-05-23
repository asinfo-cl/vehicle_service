from odoo.tests import common, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestWorkshopVehicle(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Client'})
        cls.vehicle = cls.env['workshop.vehicle'].create({
            'license_plate': 'ABC123',
            'brand': 'Toyota',
            'model_name': 'Corolla',
            'year': 2020,
            'color': 'Red',
            'partner_id': cls.partner.id,
        })

    # ------------------------------------------------------------------
    # Basic creation
    # ------------------------------------------------------------------

    def test_vehicle_creation(self):
        self.assertEqual(self.vehicle.license_plate, 'ABC123')
        self.assertEqual(self.vehicle.brand, 'Toyota')
        self.assertEqual(self.vehicle.partner_id, self.partner)

    def test_display_name_contains_key_fields(self):
        name = self.vehicle.display_name
        self.assertIn('Toyota', name)
        self.assertIn('Corolla', name)
        self.assertIn('ABC123', name)
        self.assertIn('2020', name)

    def test_display_name_without_optional_fields(self):
        vehicle = self.env['workshop.vehicle'].create({
            'license_plate': 'MIN001',
            'partner_id': self.partner.id,
        })
        self.assertIn('MIN001', vehicle.display_name)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def test_license_plate_unique(self):
        with self.assertRaises(Exception):
            self.env['workshop.vehicle'].create({
                'license_plate': 'ABC123',
                'partner_id': self.partner.id,
            })

    # ------------------------------------------------------------------
    # Repair order count
    # ------------------------------------------------------------------

    def test_repair_order_count(self):
        self.assertEqual(self.vehicle.repair_order_count, 0)
        self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'service_type': 'repair',
            'vehicle_id': self.vehicle.id,
        })
        self.vehicle.invalidate_recordset()
        self.assertEqual(self.vehicle.repair_order_count, 1)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def test_action_view_repair_orders_returns_action(self):
        action = self.vehicle.action_view_repair_orders()
        self.assertEqual(action['res_model'], 'sale.order')
        self.assertIn(('vehicle_id', '=', self.vehicle.id), action['domain'])
