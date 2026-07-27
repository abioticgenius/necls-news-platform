import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';
import { ContentType, CONTENT_TYPE_VALUES } from '../../../types/ReqResTypes';

export class LocalizedEventData extends Model {
  declare id: string;
  declare language_id: string;
  declare event_id: string;
  declare title: string;
  declare description: string;
  declare content: object;
  declare contentType: ContentType;
  declare audio: string;
  declare audioFullStory: string;
  declare quotes: object;
}

export const LocalizedEventDataModel = {
  define: (sequelize: Sequelize) => {
    LocalizedEventData.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      language_id: {
        type: DataTypes.TEXT,
        allowNull: false,
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
      title: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      description: {
        type: DataTypes.TEXT,
        allowNull: true,
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
      audio: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
      audioFullStory: {
        type: DataTypes.TEXT,
        allowNull: true,
        field: 'audio_full_story', // Map to database column
      },
      quotes: {
        type: DataTypes.JSONB,
        allowNull: true,
      },
    }, {
      sequelize,
      modelName: 'LocalizedEventData',
      tableName: 'localized_event_data',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_id', 'language_id'],
          name: 'uq_led_event_lang',
        },
      ],
      validate: {
        validateTitle() {
          if (!this.title || (typeof this.title === 'string' && this.title.trim() === '')) {
            throw new Error('LocalizedEventData validation failed: Title is required and cannot be empty');
          }
        },
      },
    });
    return LocalizedEventData;
  },
  createAssociations: (models: AppDbModels) => {
    LocalizedEventData.belongsTo(models.Event, { foreignKey: 'event_id' });
    LocalizedEventData.belongsTo(models.Language, { foreignKey: 'language_id' });
  }
};
