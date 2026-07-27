import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class EventSeoTag extends Model {
  declare id: string;
  declare event_id: string;
  declare seo_tag_id: string;
  declare weight: number;
  declare role: 'core' | 'contextual';
  declare linked_to_tag_id: string | null;
  declare created_date: Date;
}

export const EventSeoTagModel = {
  define: (sequelize: Sequelize) => {
    EventSeoTag.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      event_id: {
        type: DataTypes.UUID,
        allowNull: false,
        references: {
          model: 'event',
          key: 'id',
        },
        onDelete: 'CASCADE',
      },
      seo_tag_id: {
        type: DataTypes.UUID,
        allowNull: false,
        references: {
          model: 'seo_tag',
          key: 'id',
        },
        onDelete: 'CASCADE',
      },
      weight: {
        type: DataTypes.INTEGER,
        allowNull: false,
        defaultValue: 50,
      },
      role: {
        type: DataTypes.ENUM('core', 'contextual'),
        allowNull: false,
        defaultValue: 'contextual',
      },
      linked_to_tag_id: {
        type: DataTypes.UUID,
        allowNull: true,
        references: {
          model: 'seo_tag',
          key: 'id',
        },
        onDelete: 'SET NULL',
      },
      created_date: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: Sequelize.fn('now'),
      },
    }, {
      sequelize,
      modelName: 'EventSeoTag',
      tableName: 'event_seo_tag',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_id', 'seo_tag_id'],
          name: 'uq_event_seo_tag_event_tag',
        }
      ],
    });
    return EventSeoTag;
  },
  createAssociations: (models: AppDbModels) => {
    EventSeoTag.belongsTo(models.Event, { foreignKey: 'event_id' });
    EventSeoTag.belongsTo(models.SeoTag, { foreignKey: 'seo_tag_id' });
    EventSeoTag.belongsTo(models.SeoTag, { foreignKey: 'linked_to_tag_id', as: 'LinkedToTag' });
  }
};

