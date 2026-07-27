import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class Category extends Model {
  // Remove public class fields to avoid shadowing Sequelize getters/setters
  declare id: string;
  declare name: string;
}

export const CategoryModel = {
  define: (sequelize: Sequelize) => {
    Category.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      name: {
        type: DataTypes.TEXT,
        allowNull: false,
        unique: true,
      },
    }, {
      sequelize,
      modelName: 'Category',
      tableName: 'category',
      timestamps: false,
    });
    return Category;
  },
  createAssociations: (models: AppDbModels) => {
    Category.hasMany(models.Event, { foreignKey: 'category_id' });
  }
};
