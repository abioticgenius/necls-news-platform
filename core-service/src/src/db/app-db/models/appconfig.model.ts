import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class AppConfig extends Model {
  declare id: number;
  declare config_key: string;
  declare config_value: any; // JSONB - can be any JSON value
  declare description: string | null;
  declare updated_at: Date;
}

export const AppConfigModel = {
  define: (sequelize: Sequelize) => {
    AppConfig.init({
      id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
      },
      config_key: {
        type: DataTypes.TEXT,
        allowNull: false,
        unique: true,
        validate: {
          notEmpty: true,
        },
      },
      config_value: {
        type: DataTypes.JSONB,
        allowNull: false,
      },
      description: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
      updated_at: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: Sequelize.fn('now'),
      },
    }, {
      sequelize,
      modelName: 'AppConfig',
      tableName: 'app_config',
      timestamps: true,
      createdAt: false, // No created_at column
      updatedAt: 'updated_at',
      indexes: [
        {
          fields: ['config_key'],
          name: 'idx_app_config_key',
        },
      ],
    });
    return AppConfig;
  },
  createAssociations: (models: AppDbModels) => {
    // No associations needed for this table
  }
};

