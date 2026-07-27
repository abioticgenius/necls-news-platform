import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class EventFaq extends Model {
  declare id: string;
  declare event_id: string;
  declare language_id: string;
  declare question: string;
  declare answer: string;
  declare sequence: number;
  declare created_date: Date;
}

export const EventFaqModel = {
  define: (sequelize: Sequelize) => {
    EventFaq.init({
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
      language_id: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      question: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      answer: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      sequence: {
        type: DataTypes.SMALLINT,
        allowNull: false,
        defaultValue: 0,
      },
      created_date: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: Sequelize.fn('now'),
      },
    }, {
      sequelize,
      modelName: 'EventFaq',
      tableName: 'event_faq',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_id', 'language_id', 'question'],
          name: 'uq_event_faq_event_lang_question',
        },
      ],
    });
    return EventFaq;
  },
  createAssociations: (models: AppDbModels) => {
    EventFaq.belongsTo(models.Event, { foreignKey: 'event_id', as: 'Event' });
    EventFaq.belongsTo(models.Language, { foreignKey: 'language_id' });
  },
};

