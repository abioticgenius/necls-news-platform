import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export type UserMilestones = {
  streak: {
    current: number;
    rest_days_used_this_week: number;
    last_activity_date: string | null;
  };
  articles_read: { total: number };
  shares_made: { total: number };
  assistant_queries: { total: number };
};

export class User extends Model {
  declare id: string;
  declare uid: string;              // Firebase UID
  declare email: string | null;
  declare name: string | null;
  declare picture: string | null;
  declare provider: string | null;  // google.com | password | apple.com
  declare locale: string | null;
  declare interests: string[] | null;
  declare activity_dates: string[] | null;
  declare milestones: UserMilestones | null;
  declare earned_badges: number[] | null;  // Array of badge IDs
  declare createdAt: Date;
  declare updatedAt: Date;
}

export const UserModel = {
  define: (sequelize: Sequelize) => {
    User.init(
      {
        id: {
          type: DataTypes.UUID,
          defaultValue: DataTypes.UUIDV4,
          primaryKey: true,
        },

        uid: {
          type: DataTypes.TEXT,
          allowNull: false,
          unique: true,
        },

        email: {
          type: DataTypes.TEXT,
          allowNull: true,
          validate: { isEmail: true },
        },

        name: {
          type: DataTypes.TEXT,
          allowNull: true,
        },

        picture: {
          type: DataTypes.TEXT,
          allowNull: true,
        },

        provider: {
          type: DataTypes.TEXT,
          allowNull: true,
        },

        locale: {
          type: DataTypes.TEXT,
          allowNull: true,
        },
        interests: {
          type: DataTypes.JSONB,
          allowNull: true,
          defaultValue: [],
        },
        activity_dates: {
          type: DataTypes.ARRAY(DataTypes.DATEONLY),
          allowNull: true,
          defaultValue: [],
        },
        milestones: {
          type: DataTypes.JSONB,
          allowNull: true,
          defaultValue: null,
        },
        earned_badges: {
          type: DataTypes.ARRAY(DataTypes.INTEGER),
          allowNull: true,
          defaultValue: [],
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
        modelName: 'User',
        tableName: 'users',
        timestamps: true,
      }
    );

    return User;
  },

  createAssociations: (models: AppDbModels) => {
    // add later:
    User.hasMany(models.Bookmark, { foreignKey: 'user_id' });
    User.hasMany(models.Collection, { foreignKey: 'user_id' });
    User.hasMany(models.UserDevice, {
      foreignKey: 'user_id',
      as: 'devices',
    });
  },
};
