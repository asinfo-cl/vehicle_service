from odoo.tests import common, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestSaleOrderRepair(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Client'})
        cls.partner2 = cls.env['res.partner'].create({'name': 'Other Client'})
        cls.vehicle = cls.env['workshop.vehicle'].create({
            'license_plate': 'XYZ789',
            'brand': 'Honda',
            'model_name': 'Civic',
            'partner_id': cls.partner.id,
        })

    def _create_repair_order(self, **kwargs):
        vals = {
            'partner_id': self.partner.id,
            'service_type': 'repair',
            'vehicle_id': self.vehicle.id,
        }
        vals.update(kwargs)
        return self.env['sale.order'].create(vals)

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def test_repair_order_defaults(self):
        order = self._create_repair_order()
        self.assertEqual(order.service_type, 'repair')
        self.assertEqual(order.vehicle_id, self.vehicle)
        self.assertEqual(order.repair_status, 'diagnosis')

    def test_repair_order_gets_ro_sequence(self):
        order = self._create_repair_order()
        self.assertNotEqual(order.name, 'New')
        self.assertTrue(order.name)

    def test_repair_sections_created_on_create(self):
        order = self._create_repair_order()
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertGreater(len(sections), 0)
        section_cats = sections.mapped('line_category')
        for cat in ('labor', 'parts'):
            self.assertIn(cat, section_cats)

    def test_normal_sale_has_no_sections(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'service_type': 'sale',
        })
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(sections), 0)

    # ------------------------------------------------------------------
    # Service type switching
    # ------------------------------------------------------------------

    def test_switch_to_sale_removes_sections(self):
        order = self._create_repair_order()
        order.write({'service_type': 'sale'})
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(sections), 0)

    def test_switch_to_repair_adds_sections(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'service_type': 'sale',
        })
        order.write({'service_type': 'repair'})
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertGreater(len(sections), 0)

    # ------------------------------------------------------------------
    # Reception actions
    # ------------------------------------------------------------------

    def test_accept_reception(self):
        order = self._create_repair_order()
        self.assertFalse(order.reception_accepted)
        order.action_accept_reception()
        self.assertTrue(order.reception_accepted)
        self.assertTrue(order.reception_accepted_date)

    # ------------------------------------------------------------------
    # Report helper
    # ------------------------------------------------------------------

    def test_get_order_lines_to_report_omits_empty_sections(self):
        order = self._create_repair_order()
        # No detail lines added — all sections should be omitted from report
        reportable = order._get_order_lines_to_report()
        section_lines = reportable.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(section_lines), 0)
