import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class Event extends Model {
  declare id: string;
  declare image: string;
  declare image_source_url: string;
  declare article_type: string;
  declare time_stamp: Date;
  declare created_date: Date;

  // Association properties
  declare Sources?: any[];
  declare LocalizedEventData?: any[];
  declare SeoTags?: any[];
  declare EventAnalysis?: any[];
  declare EventSoFar?: any[];
  declare localizedData?: any[];
}

export const EventModel = {
  define: (sequelize: Sequelize) => {
    Event.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      image: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
      image_source_url: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
      article_type: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
      time_stamp: {
        type: DataTypes.DATE,
        allowNull: true,
      },
      created_date: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: Sequelize.fn('now'),
      },
    }, {
      sequelize,
      modelName: 'Event',
      tableName: 'event',
      timestamps: false,
    });
    return Event;
  },
  createAssociations: (models: AppDbModels) => {
    // One-to-Many
    Event.hasMany(models.EventAnalysis, { foreignKey: 'event_id', as: 'EventAnalysis' });
    Event.hasMany(models.EventSoFar, { foreignKey: 'event_id', as: 'EventSoFar' });
    Event.hasMany(models.Source, { foreignKey: 'event_id', as: 'Sources' });
    Event.hasMany(models.LocalizedEventData, { foreignKey: 'event_id', as: 'localizedData' });
    Event.hasMany(models.EventSeoTag, { foreignKey: 'event_id', as: 'EventSeoTags' });
    Event.belongsToMany(models.SeoTag, { through: models.EventSeoTag, foreignKey: 'event_id', otherKey: 'seo_tag_id', as: 'SeoTags' });
  },
};
