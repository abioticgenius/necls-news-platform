import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';
import { ContentType, CONTENT_TYPE_VALUES } from '../../../types/ReqResTypes';

export class LocalizedEventSoFar extends Model {
  declare id: string;
  declare language_id: string;
  declare event_so_far_id: string;
  declare content: object;
  declare contentType: ContentType;
}

export const LocalizedEventSoFarModel = {
  define: (sequelize: Sequelize) => {
    LocalizedEventSoFar.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      language_id: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      event_so_far_id: {
        type: DataTypes.UUID,
        allowNull: false,
        references: {
          model: 'event_so_far',
          key: 'id',
        },
        onDelete: 'CASCADE',
      },
      content: {
        type: DataTypes.JSONB,
        allowNull: true,
      },
      contentType: {
        type: DataTypes.ENUM(...CONTENT_TYPE_VALUES),
        allowNull: true,
        field: 'content_type', // Map to database column
      },
    }, {
      sequelize,
      modelName: 'LocalizedEventSoFar',
      tableName: 'localized_event_so_far',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_so_far_id', 'language_id'],
          name: 'uq_lesf_event_lang',
        },
      ],
    });
    return LocalizedEventSoFar;
  },
  createAssociations: (models: AppDbModels) => {
    LocalizedEventSoFar.belongsTo(models.EventSoFar, { foreignKey: 'event_so_far_id' });
    LocalizedEventSoFar.belongsTo(models.Language, { foreignKey: 'language_id' });
  }
};
