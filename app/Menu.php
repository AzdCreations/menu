<?php

namespace App;

use Illuminate\Database\Eloquent\Model;

class Menu extends Model
{
    protected $fillable=['img','title','more','status','user_id'];

    public function user()
    {
        return $this->belongsTo(User::class);
    }
}
