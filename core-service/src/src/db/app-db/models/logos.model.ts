import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class Logos extends Model {
  declare id: string;
  declare name: string;
  declare website: string;
  declare favicon_s3_path: string | null;
  declare logo_s3_path: string | null;
}

export const LogosModel = {
  define: (sequelize: Sequelize) => {
    Logos.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      name: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      website: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      favicon_s3_path: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
      logo_s3_path: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
    }, {
      sequelize,
      modelName: 'Logos',
      tableName: 'logos',
      timestamps: false,
    });
    return Logos;
  },
  createAssociations: (models: AppDbModels) => {
    // Add associations here if needed
  }
};
