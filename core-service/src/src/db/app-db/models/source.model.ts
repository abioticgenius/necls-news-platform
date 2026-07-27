import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';
import type { Logos } from './logos.model';

export class Source extends Model {
  declare id: string;
  declare title: string;
  declare logo_id: string;
  declare event_id: string;
  declare source_url: string;
  declare Logo?: Logos | null;
}

export const SourceModel = {
  define: (sequelize: Sequelize) => {
    Source.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      logo_id: {
        type: DataTypes.UUID,
        allowNull: true,
        references: {
          model: 'logos',
          key: 'id',
        },
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
      source_url: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      title: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
    }, {
      sequelize,
      modelName: 'Source',
      tableName: 'source',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_id', 'source_url'],
          name: 'uq_source_event_url',
        },
      ],
    });
    return Source;
  },
  createAssociations: (models: AppDbModels) => {
    Source.belongsTo(models.Event, { foreignKey: 'event_id' });
    Source.belongsTo(models.Logos, { foreignKey: 'logo_id', as: 'Logo' });
  }
};
