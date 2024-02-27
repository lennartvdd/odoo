# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_stock_landed_costs = fields.Boolean("Landed Costs",
        help="Affect landed costs on reception operations and split them among products to update their cost price.")
    group_lot_on_invoice = fields.Boolean("Display Lots & Serial Numbers on Invoices",
                                          implied_group='stock_account.group_lot_on_invoice')
    group_stock_accounting_automatic = fields.Boolean(
        "Automatic Stock Accounting", implied_group="stock_account.group_stock_accounting_automatic")
    
    inventory_revaluation_distribution_method = fields.Selection(related='company_id.inventory_revaluation_distribution_method', string='Revaluation Distribution Method', readonly=False, required=True)

    def set_values(self):
        automatic_before = self.env.user.has_group('stock_account.group_stock_accounting_automatic')
        super().set_values()
        if automatic_before and not self.group_stock_accounting_automatic:
            self.env['product.category'].sudo().with_context(active_test=False).search([
                ('property_valuation', '=', 'real_time')]).property_valuation = 'manual_periodic'
