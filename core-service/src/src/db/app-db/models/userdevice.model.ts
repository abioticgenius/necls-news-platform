import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class UserDevice extends Model {
  declare id: string;
  declare user_id: string;

  declare device_id: string;       // stable install/device id
  declare fcm_token: string;       // current FCM token
  declare platform: 'ios' | 'android' | 'web';

  declare app_version: string | null;
  declare last_active_at: Date | null;
  declare is_active: boolean;

  declare createdAt: Date;
  declare updatedAt: Date;
}

export const UserDeviceModel = {
  define: (sequelize: Sequelize) => {
    UserDevice.init(
      {
        id: {
          type: DataTypes.UUID,
          defaultValue: DataTypes.UUIDV4,
          primaryKey: true,
        },

        user_id: {
          type: DataTypes.UUID,
          allowNull: false,
        },

        device_id: {
          type: DataTypes.TEXT,
          allowNull: false,
        },

        fcm_token: {
          type: DataTypes.TEXT,
          allowNull: false
        },

        platform: {
          type: DataTypes.ENUM('ios', 'android', 'web'),
          allowNull: false,
        },

        app_version: {
          type: DataTypes.TEXT,
          allowNull: true,
        },

        last_active_at: {
          type: DataTypes.DATE,
          allowNull: true,
        },

        is_active: {
          type: DataTypes.BOOLEAN,
          allowNull: false,
          defaultValue: true,
        },

        createdAt: {
          type: DataTypes.DATE,
          allowNull: false,
        },

        updatedAt: {
          type: DataTypes.DATE,
          allowNull: false,
        },
      },
      {
        sequelize,
        modelName: 'UserDevice',
        tableName: 'user_devices',
        timestamps: true,
        indexes: [
          {
            unique: true,
            fields: ['user_id', 'device_id'],
          },
        ],
      }
    );

    return UserDevice;
  },

  createAssociations: (models: AppDbModels) => {
    UserDevice.belongsTo(models.User, {
      foreignKey: 'user_id',
      as: 'user',
    });
  },
};