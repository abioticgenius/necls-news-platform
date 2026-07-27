import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class AssistantChunk extends Model {
  declare id: string;
  declare event_id: string;
  declare chunk_text: string;
  declare embedding: number[]; // Vector as array
  declare chunk_type: 'title' | 'description' | 'content' | 'story_so_far' | 'analysis';
  declare sequence: number;
  declare title: string;
  declare created_at: Date;
  declare updated_at: Date;
  
  // Association properties
  declare Event?: any;
}

export const AssistantChunkModel = {
  define: (sequelize: Sequelize) => {
    AssistantChunk.init({
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
      chunk_text: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      // embedding (vector(384)) is managed by migrations only.
      // Declaring it here would cause Sequelize to revert the column type to real[].

      chunk_type: {
        type: DataTypes.ENUM('title', 'description', 'content', 'story_so_far', 'analysis'),
        allowNull: false,
        field: 'chunk_type',
      },
      sequence: {
        type: DataTypes.INTEGER,
        allowNull: false,
        defaultValue: 0,
      },
      title: {
        type: DataTypes.TEXT,
        allowNull: true,
      },
      created_at: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
      },
      updated_at: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
      },
    }, {
      sequelize,
      modelName: 'AssistantChunk',
      tableName: 'assistant_chunks',
      timestamps: true,
      createdAt: 'created_at',
      updatedAt: 'updated_at',
      indexes: [
        {
          fields: ['event_id'],
          name: 'idx_assistant_chunks_event',
        },
      ],
    });
    return AssistantChunk;
  },
  createAssociations: (models: AppDbModels) => {
    AssistantChunk.belongsTo(models.Event, { foreignKey: 'event_id', as: 'Event' });
  }
};





