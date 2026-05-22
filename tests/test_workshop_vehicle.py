from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestWorkshopVehicle(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Client',
        })
        cls.vehicle = cls.env['workshop.vehicle'].create({
            'license_plate': 'ABC123',
            'brand': 'Toyota',
            'model_name': 'Corolla',
            'year': 2020,
            'color': 'Rojo',
            'partner_id': cls.partner.id,
        })

    def test_vehicle_creation(self):
        self.assertEqual(self.vehicle.license_plate, 'ABC123')
        self.assertEqual(self.vehicle.brand, 'Toyota')
        self.assertEqual(self.vehicle.partner_id, self.partner)

    def test_vehicle_display_name(self):
        self.assertIn('Toyota', self.vehicle.display_name)
        self.assertIn('Corolla', self.vehicle.display_name)
        self.assertIn('ABC123', self.vehicle.display_name)

    def test_license_plate_unique(self):
        with self.assertRaises(Exception):
            self.env['workshop.vehicle'].create({
                'license_plate': 'ABC123',
                'partner_id': self.partner.id,
            })
