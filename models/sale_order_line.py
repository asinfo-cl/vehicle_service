from odoo import models, fields, api

# Sequences for section and detail lines per category
_SECTION_SEQ = {
    'labor': 1, 'parts': 101, 'third_party': 201, 'supplies': 301, 'others': 401,
}
_DETAIL_SEQ = {
    'labor': 10, 'parts': 110, 'third_party': 210, 'supplies': 310, 'others': 410,
}

LINE_CATEGORY_SELECTION = [
    ('labor', 'Labor'),
    ('parts', 'Parts'),
    ('third_party', 'Third Party'),
    ('supplies', 'Supplies'),
    ('others', 'Others'),
]


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    line_category = fields.Selection(
        LINE_CATEGORY_SELECTION,
        string='Category',
        default='others',
    )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _expected_sequence(self):
        """Return the expected sequence for this line based on category and type."""
        self.ensure_one()
        seq_map = _SECTION_SEQ if self.display_type == 'line_section' else _DETAIL_SEQ
        return seq_map.get(self.line_category, 1000)

    def _fix_repair_sequences(self):
        """Correct sequences for repair order lines — avoids per-line writes when unchanged."""
        repair_lines = self.filtered(lambda l: l.order_id.service_type == 'repair')
        for line in repair_lines:
            expected = line._expected_sequence()
            if line.sequence != expected:
                line.sequence = expected

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._fix_repair_sequences()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if 'line_category' in vals or 'display_type' in vals:
            self._fix_repair_sequences()
        return result
