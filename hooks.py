def post_init_hook(env):
    groups = env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
    models = env['ir.model'].search([('model', 'like', 'workshop.%')])
    if groups and models:
        groups.write({'model_access': [(4, m.id) for m in models]})
