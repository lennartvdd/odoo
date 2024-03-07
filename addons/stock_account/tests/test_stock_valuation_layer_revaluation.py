# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tools import float_compare
from odoo.addons.stock_account.tests.test_stockvaluation import _create_accounting_data
from odoo.addons.stock_account.tests.test_stockvaluationlayer import TestStockValuationCommon


class TestStockValuationLayerRevaluation(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super(TestStockValuationLayerRevaluation, cls).setUpClass()
        cls.stock_input_account, cls.stock_output_account, cls.stock_valuation_account, cls.expense_account, cls.stock_journal = _create_accounting_data(cls.env)
        cls.product1.write({
            'property_account_expense_id': cls.expense_account.id,
        })
        cls.product1.categ_id.write({
            'property_valuation': 'real_time',
            'property_stock_account_input_categ_id': cls.stock_input_account.id,
            'property_stock_account_output_categ_id': cls.stock_output_account.id,
            'property_stock_valuation_account_id': cls.stock_valuation_account.id,
            'property_stock_journal': cls.stock_journal.id,
        })

        cls.product1.categ_id.property_valuation = 'real_time'

    def test_stock_valuation_layer_revaluation_avco(self):
        self.product1.categ_id.property_cost_method = 'average'

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 10, unit_cost=2)
        self._make_in_move(self.product1, 10, unit_cost=4)

        self.assertEqual(self.product1.standard_price, 3)
        self.assertEqual(self.product1.quantity_svl, 20)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 2)
        self.assertEqual(old_layers[0].remaining_value, 40)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = 20
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_avco"
        revaluation_wizard.save().action_validate_revaluation()

        # Check standard price change
        self.assertEqual(self.product1.standard_price, 4)
        self.assertEqual(self.product1.quantity_svl, 20)

        # Check the creation of stock.valuation.layer
        new_layer = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc", limit=1)
        self.assertEqual(new_layer.value, 20)
        self.assertEqual(new_layer.description, f"Manual Stock Valuation: unit_test_avco. Product cost updated from 3.0 to 4.0.")

        # Check the remaing value of current layers
        self.assertEqual(old_layers[0].remaining_value, 50)
        self.assertEqual(sum(slv.remaining_value for slv in old_layers), 80)

        # Check account move
        self.assertTrue(bool(new_layer.account_move_id))
        self.assertEqual(len(new_layer.account_move_id.line_ids), 2)

        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("debit")), 20)
        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("credit")), 20)

        credit_lines = [l for l in new_layer.account_move_id.line_ids if l.credit > 0]
        self.assertEqual(len(credit_lines), 1)
        self.assertEqual(credit_lines[0].account_id.id, self.stock_valuation_account.id)

    def test_stock_valuation_layer_revaluation_avco_rounding(self):
        self.product1.categ_id.property_cost_method = 'average'

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 1, unit_cost=1)
        self._make_in_move(self.product1, 1, unit_cost=1)
        self._make_in_move(self.product1, 1, unit_cost=1)

        self.assertEqual(self.product1.standard_price, 1)
        self.assertEqual(self.product1.quantity_svl, 3)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 3)
        self.assertEqual(old_layers[0].remaining_value, 1)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = 1
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_avco_rounding"
        revaluation_wizard.save().action_validate_revaluation()

        # Check standard price change
        self.assertEqual(self.product1.standard_price, 1.33)
        self.assertEqual(self.product1.quantity_svl, 3)

        # Check the creation of stock.valuation.layer
        new_layer = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc", limit=1)
        self.assertEqual(new_layer.value, 1)
        self.assertEqual(new_layer.description, f"Manual Stock Valuation: unit_test_avco_rounding. Product cost updated from 1.0 to 1.33.")

        # Check the remaing value of current layers
        self.assertEqual(sum(slv.remaining_value for slv in old_layers), 4)
        self.assertTrue(1.34 in old_layers.mapped("remaining_value"))

        # Check account move
        self.assertTrue(bool(new_layer.account_move_id))
        self.assertEqual(len(new_layer.account_move_id.line_ids), 2)

        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("debit")), 1)
        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("credit")), 1)

        credit_lines = [l for l in new_layer.account_move_id.line_ids if l.credit > 0]
        self.assertEqual(len(credit_lines), 1)
        self.assertEqual(credit_lines[0].account_id.id, self.stock_valuation_account.id)

    def test_stock_valuation_layer_revaluation_avco_rounding_2_digits(self):
        """
        Check that the rounding of the new price (cost) is equivalent to the rounding of the standard price (cost)
        The check is done indirectly via the layers valuations.
        If correct => rounding method is correct too
        """
        self.product1.categ_id.property_cost_method = 'average'

        self.env['decimal.precision'].search([
            ('name', '=', 'Product Price'),
        ]).digits = 2
        self.product1.write({'standard_price': 0})

        # First Move
        self.product1.write({'standard_price': 0.022})
        self._make_in_move(self.product1, 10000)

        self.assertEqual(self.product1.standard_price, 0.02)
        self.assertEqual(self.product1.quantity_svl, 10000)

        layer = self.product1.stock_valuation_layer_ids
        self.assertEqual(layer.value, 200)

        # Second Move
        self.product1.write({'standard_price': 0.053})

        self.assertEqual(self.product1.standard_price, 0.05)
        self.assertEqual(self.product1.quantity_svl, 10000)

        layers = self.product1.stock_valuation_layer_ids
        self.assertEqual(layers[0].value, 200)
        self.assertEqual(layers[1].value, 300)

    def test_stock_valuation_layer_revaluation_avco_rounding_5_digits(self):
        """
        Check that the rounding of the new price (cost) is equivalent to the rounding of the standard price (cost)
        The check is done indirectly via the layers valuations.
        If correct => rounding method is correct too
        """
        self.product1.categ_id.property_cost_method = 'average'

        self.env['decimal.precision'].search([
            ('name', '=', 'Product Price'),
        ]).digits = 5

        # First Move
        self.product1.write({'standard_price': 0.00875})
        self._make_in_move(self.product1, 10000)

        self.assertEqual(self.product1.standard_price, 0.00875)
        self.assertEqual(self.product1.quantity_svl, 10000)

        layer = self.product1.stock_valuation_layer_ids
        self.assertEqual(layer.value, 87.5)

        # Second Move
        self.product1.write({'standard_price': 0.00975})

        self.assertEqual(self.product1.standard_price, 0.00975)
        self.assertEqual(self.product1.quantity_svl, 10000)

        layers = self.product1.stock_valuation_layer_ids
        self.assertEqual(layers[0].value, 87.5)
        self.assertEqual(layers[1].value, 10)

    def test_stock_valuation_layer_revaluation_fifo(self):
        self.product1.categ_id.property_cost_method = 'fifo'

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 10, unit_cost=2)
        self._make_in_move(self.product1, 10, unit_cost=4)

        self.assertEqual(self.product1.standard_price, 2)
        self.assertEqual(self.product1.quantity_svl, 20)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 2)
        self.assertEqual(old_layers[0].remaining_value, 40)
        self.assertEqual(sum(slv.remaining_value for slv in old_layers), 60)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = 20
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_fifo"
        revaluation_wizard.save().action_validate_revaluation()

        self.assertEqual(self.product1.standard_price, 3)

        # Check the creation of stock.valuation.layer
        new_layer = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc", limit=1)
        self.assertEqual(new_layer.value, 20)
        self.assertEqual(new_layer.description, f"Manual Stock Valuation: unit_test_fifo. Product cost updated from 2.0 to 3.0.")

        # Check the remaing value of current layers
        self.assertEqual(old_layers[0].remaining_value, 50)
        self.assertEqual(sum(slv.remaining_value for slv in old_layers), 80)

        # Check account move
        self.assertTrue(bool(new_layer.account_move_id))
        self.assertTrue(len(new_layer.account_move_id.line_ids), 2)

        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("debit")), 20)
        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("credit")), 20)

        credit_lines = [l for l in new_layer.account_move_id.line_ids if l.credit > 0]
        self.assertEqual(len(credit_lines), 1)

    def test_devaluation_fifo_by_quantity(self):
        self.product1.categ_id.property_cost_method = 'fifo'

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 10, unit_cost=2)
        self._make_in_move(self.product1, 10, unit_cost=4)

        self.assertEqual(self.product1.standard_price, 2)
        self.assertEqual(self.product1.quantity_svl, 20)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 2)
        self.assertEqual(old_layers[0].remaining_value, 40)
        self.assertEqual(sum(slv.remaining_value for slv in old_layers), 60)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = -20
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_fifo_devaluation_valid"
        revaluation_wizard.save().action_validate_revaluation()

        self.assertEqual(self.product1.standard_price, 1)

        # Check the creation of stock.valuation.layer
        new_layer = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc", limit=1)
        self.assertEqual(new_layer.value, -20)
        self.assertEqual(new_layer.description, f"Manual Stock Valuation: unit_test_fifo_devaluation_valid. Product cost updated from 2.0 to 1.0.")

        # Check the remaing value of current layers
        self.assertEqual(old_layers[0].remaining_value, 30)
        self.assertEqual(sum(slv.remaining_value for slv in old_layers), 40)

        # Check account move
        self.assertTrue(bool(new_layer.account_move_id))
        self.assertTrue(len(new_layer.account_move_id.line_ids), 2)

        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("debit")), 20)
        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("credit")), 20)

        credit_lines = [l for l in new_layer.account_move_id.line_ids if l.credit > 0]
        self.assertEqual(len(credit_lines), 1)

    def test_devaluation_avco_by_quantity(self):
        self.product1.categ_id.property_cost_method = 'average'

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 10, unit_cost=2)
        self._make_in_move(self.product1, 10, unit_cost=4)

        self.assertEqual(self.product1.standard_price, 3)
        self.assertEqual(self.product1.quantity_svl, 20)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 2)
        self.assertEqual(old_layers[0].remaining_value, 40)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = -20
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_fifo_devaluation_valid"
        revaluation_wizard.save().action_validate_revaluation()

        self.assertEqual(self.product1.standard_price, 2)

        # Check the creation of stock.valuation.layer
        new_layer = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc", limit=1)
        self.assertEqual(new_layer.value, -20)
        self.assertEqual(new_layer.description, f"Manual Stock Valuation: unit_test_fifo_devaluation_valid. Product cost updated from 3.0 to 2.0.")

        # Check the remaing value of current layers
        self.assertEqual(old_layers[0].remaining_value, 30)
        self.assertEqual(sum(slv.remaining_value for slv in old_layers), 40)

        # Check account move
        self.assertTrue(bool(new_layer.account_move_id))
        self.assertTrue(len(new_layer.account_move_id.line_ids), 2)

        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("debit")), 20)
        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("credit")), 20)

        credit_lines = [l for l in new_layer.account_move_id.line_ids if l.credit > 0]
        self.assertEqual(len(credit_lines), 1)

    def test_devaluation_fifo_by_quantity_negative_error(self):
        self.product1.categ_id.property_cost_method = 'fifo'
        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 17, unit_cost=0.79)
        self._make_in_move(self.product1, 12, unit_cost=5.77)
        self._make_in_move(self.product1, 2, unit_cost=5.77)

        self.assertEqual(float_compare(self.product1.standard_price, 0.79, precision_digits=4), 0)
        self.assertEqual(self.product1.quantity_svl, 31)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 3)
        self.assertEqual(float_compare(sum(slv.remaining_value for slv in old_layers), 94.2100, precision_digits=4), 0)

        self.assertEqual(float_compare(old_layers[0].remaining_value, 11.5400, precision_digits=4), 0)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = -80
        revaluation_wizard.reason = "unit_test_fifo_devaluation_invalid"
        revaluation_wizard.account_id = self.stock_valuation_account

        # Remaining value for the cheapest stock valuation layer will become < 0 with distribution proportional to quantities. raise
        with self.assertRaises(UserError):
            revaluation_wizard.save().action_validate_revaluation()

    def test_devaluation_avco_by_quantity_negative_error(self):
        self.product1.categ_id.property_cost_method = 'average'

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 17, unit_cost=0.79)
        self._make_in_move(self.product1, 12, unit_cost=5.77)
        self._make_in_move(self.product1, 2, unit_cost=5.77)

        self.assertEqual(float_compare(self.product1.standard_price, 3.0400, precision_digits=4), 0)
        self.assertEqual(self.product1.quantity_svl, 31)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 3)
        self.assertEqual(float_compare(sum(slv.remaining_value for slv in old_layers), 94.2100, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[0].remaining_value, 11.5400, precision_digits=4), 0)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = -80
        revaluation_wizard.reason = "unit_test_avco_devaluation_invalid"
        revaluation_wizard.account_id = self.stock_valuation_account

        # Remaining value for the cheapest stock valuation layer will become < 0 with distribution proportional to quantities. raise
        with self.assertRaises(UserError):
            revaluation_wizard.save().action_validate_revaluation()

    def test_devaluation_invalid_system_param(self):
        self.env['ir.config_parameter'].set_param('stock_account.distribution_method', 'invalid')
        self.product1.categ_id.property_cost_method = 'fifo'

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 17, unit_cost=0.79)
        self._make_in_move(self.product1, 12, unit_cost=5.77)
        self._make_in_move(self.product1, 2, unit_cost=5.77)

        self.assertEqual(float_compare(self.product1.standard_price, 0.7900, precision_digits=4), 0)
        self.assertEqual(self.product1.quantity_svl, 31)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 3)
        self.assertEqual(float_compare(sum(slv.remaining_value for slv in old_layers), 94.2100, precision_digits=4), 0)

        self.assertEqual(float_compare(old_layers[0].remaining_value, 11.5400, precision_digits=4), 0)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = -80
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_fifo_distribute_by_value"
        
        with self.assertRaises(UserError):
            revaluation_wizard.save().action_validate_revaluation()

    def test_devaluation_fifo_by_value(self):
        self.product1.categ_id.property_cost_method = 'fifo'
        self.env['ir.config_parameter'].set_param('stock_account.distribution_method', 'value')

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 17, unit_cost=0.79)
        self._make_in_move(self.product1, 12, unit_cost=5.77)
        self._make_in_move(self.product1, 2, unit_cost=5.77)

        self.assertEqual(float_compare(self.product1.standard_price, 0.7900, precision_digits=4), 0)
        self.assertEqual(self.product1.quantity_svl, 31)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 3)
        self.assertEqual(float_compare(sum(slv.remaining_value for slv in old_layers), 94.2100, precision_digits=4), 0)

        self.assertEqual(float_compare(old_layers[0].remaining_value, 11.5400, precision_digits=4), 0)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = -80
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_fifo_distribute_by_value"
        revaluation_wizard.save().action_validate_revaluation()

        self.assertEqual(float_compare(self.product1.standard_price, 0.1200, precision_digits=4), 0)

        # Check the creation of stock.valuation.layer
        new_layer = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc", limit=1)
        self.assertEqual(new_layer.value, -80)
        self.assertEqual(new_layer.description, f"Manual Stock Valuation: unit_test_fifo_distribute_by_value. Product cost updated from 0.79 to 0.12.")

        # Check the remaing value of current layers
        self.assertEqual(float_compare(sum(slv.remaining_value for slv in old_layers), 14.2100, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[0].remaining_value, 1.7400, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[1].remaining_value, 10.4400, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[2].remaining_value, 2.0300, precision_digits=4), 0)

        # Check account move
        self.assertTrue(bool(new_layer.account_move_id))
        self.assertTrue(len(new_layer.account_move_id.line_ids), 2)

        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("debit")), 80)
        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("credit")), 80)

        credit_lines = [l for l in new_layer.account_move_id.line_ids if l.credit > 0]
        self.assertEqual(len(credit_lines), 1)

    def test_devaluation_avco_by_value(self):
        self.product1.categ_id.property_cost_method = 'average'
        self.env['ir.config_parameter'].set_param('stock_account.distribution_method', 'value')

        context = {
            'default_product_id': self.product1.id,
            'default_company_id': self.env.company.id,
            'default_added_value': 0.0
        }
        # Quantity of product1 is zero, raise
        with self.assertRaises(UserError):
            Form(self.env['stock.valuation.layer.revaluation'].with_context(context)).save()

        self._make_in_move(self.product1, 17, unit_cost=0.79)
        self._make_in_move(self.product1, 12, unit_cost=5.77)
        self._make_in_move(self.product1, 2, unit_cost=5.77)

        self.assertEqual(float_compare(self.product1.standard_price, 3.0400, precision_digits=4), 0)
        self.assertEqual(self.product1.quantity_svl, 31)

        old_layers = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc")

        self.assertEqual(len(old_layers), 3)
        self.assertEqual(float_compare(sum(slv.remaining_value for slv in old_layers), 94.2100, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[0].remaining_value, 11.5400, precision_digits=4), 0)

        revaluation_wizard = Form(self.env['stock.valuation.layer.revaluation'].with_context(context))
        revaluation_wizard.added_value = -80
        revaluation_wizard.account_id = self.stock_valuation_account
        revaluation_wizard.reason = "unit_test_avco_distribute_by_value"
        revaluation_wizard.save().action_validate_revaluation()

        # Check standard price change
        self.assertEqual(float_compare(self.product1.standard_price, 0.4600, precision_digits=4), 0)
        self.assertEqual(self.product1.quantity_svl, 31)

        # Check the creation of stock.valuation.layer
        new_layer = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)], order="create_date desc, id desc", limit=1)
        self.assertEqual(new_layer.value, -80)
        self.assertEqual(new_layer.description, f"Manual Stock Valuation: unit_test_avco_distribute_by_value. Product cost updated from 3.04 to 0.46.")

        # Check the remaing value of current layers
        self.assertEqual(float_compare(sum(slv.remaining_value for slv in old_layers), 14.2100, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[0].remaining_value, 1.7400, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[1].remaining_value, 10.4400, precision_digits=4), 0)
        self.assertEqual(float_compare(old_layers[2].remaining_value, 2.0300, precision_digits=4), 0)

        # Check account move
        self.assertTrue(bool(new_layer.account_move_id))
        self.assertEqual(len(new_layer.account_move_id.line_ids), 2)

        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("debit")), 80)
        self.assertEqual(sum(new_layer.account_move_id.line_ids.mapped("credit")), 80)

        credit_lines = [l for l in new_layer.account_move_id.line_ids if l.credit > 0]
        self.assertEqual(len(credit_lines), 1)
        self.assertEqual(credit_lines[0].account_id.id, self.stock_valuation_account.id)
